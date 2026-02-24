"""
Metadata services — extracted from arm/ui/metadata.py and arm/ui/utils.py.

All app.logger calls replaced with standard logging.
"""
import urllib
import json
import re
import logging

import requests

import arm.config.config as cfg
from arm.models.job import Job
from arm.database import db

log = logging.getLogger(__name__)

TMDB_YEAR_REGEX = r"-\d{0,2}-\d{0,2}"


def call_omdb_api(title=None, year=None, imdb_id=None, plot="short"):
    """
    Queries OMDbapi.org for title information and parses if it's a movie
        or a tv series
    """
    omdb_api_key = cfg.arm_config['OMDB_API_KEY']
    title_info = None
    str_url = f"https://www.omdbapi.com/?s={title}&plot={plot}&r=json&apikey={omdb_api_key}"
    if imdb_id:
        str_url = f"https://www.omdbapi.com/?i={imdb_id}&plot={plot}&r=json&apikey={omdb_api_key}"
    elif title:
        title = urllib.parse.quote(title)
        if year and year is not None:
            year = urllib.parse.quote(year)
            str_url = f"https://www.omdbapi.com/?s={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
        else:
            str_url = f"https://www.omdbapi.com/?s={title}&plot={plot}&r=json&apikey={omdb_api_key}"
    else:
        log.debug("no params")
    try:
        title_info_json = urllib.request.urlopen(str_url).read()
        title_info = json.loads(title_info_json.decode())
        title_info['background_url'] = None
        log.debug(f"omdb - {title_info}")
        if 'Error' in title_info or title_info['Response'] == "False":
            if title and not imdb_id:
                try:
                    log.debug("omdb search failed, trying exact title match (?t=)")
                    t_url = f"https://www.omdbapi.com/?t={title}&plot={plot}&r=json&apikey={omdb_api_key}"
                    if year:
                        t_url = f"https://www.omdbapi.com/?t={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
                    fallback_json = urllib.request.urlopen(t_url, timeout=30).read()
                    fallback_info = json.loads(fallback_json.decode())
                    if 'Error' not in fallback_info and fallback_info.get('Response') == "True":
                        fallback_info['background_url'] = None
                        title_info = {"Search": [fallback_info], "Response": "True", "background_url": None}
                    else:
                        title_info = None
                except Exception as error:
                    log.error(f"omdb ?t= fallback failed with error - {error}")
                    title_info = None
            else:
                title_info = None
    except urllib.error.HTTPError as error:
        log.error(f"omdb call failed with error - {error}")
    else:
        log.debug("omdb - call was successful")
    return title_info


def get_omdb_poster(title=None, year=None, imdb_id=None, plot="short"):
    """
    Queries OMDbapi.org for the poster for movie/show
    """
    omdb_api_key = cfg.arm_config['OMDB_API_KEY']
    if imdb_id:
        str_url = f"https://www.omdbapi.com/?i={imdb_id}&plot={plot}&r=json&apikey={omdb_api_key}"
        str_url_2 = ""
    elif title:
        str_url = f"https://www.omdbapi.com/?s={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
        str_url_2 = f"https://www.omdbapi.com/?t={title}&y={year}&plot={plot}&r=json&apikey={omdb_api_key}"
    else:
        log.debug("no params")
        return None, None
    try:
        title_info_json = urllib.request.urlopen(requests.utils.requote_uri(str_url)).read()
    except Exception as error:
        log.debug(f"Failed to reach OMdb - {error}")
    else:
        title_info = json.loads(title_info_json.decode())
        if 'Error' not in title_info:
            return title_info['Search'][0]['Poster'], title_info['Search'][0]['imdbID']

        try:
            title_info_json2 = urllib.request.urlopen(requests.utils.requote_uri(str_url_2)).read()
            title_info2 = json.loads(title_info_json2.decode())
            if 'Error' not in title_info2:
                return title_info2['Poster'], title_info2['imdbID']
        except Exception as error:
            log.error(f"Failed to reach OMdb - {error}")

    return None, None


def get_tmdb_poster(search_query=None, year=None):
    """
    Queries api.themoviedb.org for the poster and backdrop for movie
    """
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    search_results, poster_base, response = tmdb_fetch_results(search_query, year, tmdb_api_key)

    if 'status_code' in search_results:
        log.debug("get_tmdb_poster failed with status_code %s", int(search_results.get('status_code', 0)))
        return None

    if search_results['total_results'] > 0:
        log.debug("TMDB movie results: %d", int(search_results['total_results']))
        return tmdb_process_poster(search_results, poster_base)

    url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={search_query}"
    response = requests.get(url)
    search_results = json.loads(response.text)
    if search_results['total_results'] > 0:
        log.debug("TMDB tv results: %d", int(search_results['total_results']))
        return tmdb_process_poster(search_results, poster_base)
    log.debug("No results found")
    return None


def tmdb_process_poster(search_results, poster_base):
    """
    Process the results from tmdb and fix results with poster
    """
    for media in search_results['results']:
        if media['poster_path'] is not None and 'release_date' in media:
            released_date = re.sub(TMDB_YEAR_REGEX, "", media['release_date'])
            log.debug("TMDB poster match: %s (%s)", str(media['title']), str(released_date))
            media['poster_url'] = f"{poster_base}{media['poster_path']}"
            media["Plot"] = media['overview']
            media['background_url'] = f"{poster_base}{media['backdrop_path']}"
            media['Type'] = "movie"
            log.debug("TMDB backdrop found for %s", str(media['title']))
            return media
    return None


def tmdb_search(search_query=None, year=None):
    """
    Queries api.themoviedb.org for movies close to the query
    """
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    search_results, poster_base, response = tmdb_fetch_results(search_query, year, tmdb_api_key)
    log.debug("TMDB search results - movie - %d results", int(search_results.get('total_results', 0)))
    if 'status_code' in search_results:
        log.error("tmdb_fetch_results failed with status_code %s", int(search_results.get('status_code', 0)))
        return None
    return_results = {}
    if search_results['total_results'] > 0:
        log.debug("tmdb_search - found %d movies", int(search_results['total_results']))
        return tmdb_process_results(poster_base, return_results, search_results, "movie")
    log.debug("tmdb_search - movie not found, trying tv series ")
    url = f"https://api.themoviedb.org/3/search/tv?api_key={tmdb_api_key}&query={search_query}"
    response = requests.get(url)
    search_results = json.loads(response.text)
    if search_results['total_results'] > 0:
        log.debug("TMDB tv results: %d", int(search_results['total_results']))
        return tmdb_process_results(poster_base, return_results, search_results, "series")

    log.debug("tmdb_search - no results found")
    return None


def tmdb_process_results(poster_base, return_results, search_results, media_type="movie"):
    """
    Process search result so that it follows omdb style of output
    """
    for result in search_results['results']:
        log.debug("Processing TMDB result: %s", str(result.get('title', result.get('name', 'unknown'))))
        result['poster_path'] = result['poster_path'] if result['poster_path'] is not None else None
        result['release_date'] = '0000-00-00' if 'release_date' not in result else result['release_date']
        result['imdbID'] = tmdb_get_imdb(result['id'])
        result['Year'] = re.sub(TMDB_YEAR_REGEX, "", result['first_air_date']) if 'first_air_date' in result else \
            re.sub(TMDB_YEAR_REGEX, "", result['release_date'])
        result['Title'] = result['title'] if 'title' in result else result['name']
        result['Type'] = media_type
        result['Poster'] = f"{poster_base}{result['poster_path']}"
        result['background_url'] = f"{poster_base}{result['backdrop_path']}"
        result["Plot"] = result['overview']
    return_results['Search'] = search_results['results']
    return return_results


def tmdb_get_imdb(tmdb_id):
    """
    Queries api.themoviedb.org for imdb_id by TMDB id
    """
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={tmdb_api_key}&" \
          f"append_to_response=alternative_titles,credits,images,keywords,releases,reviews,similar,videos,external_ids"
    url_tv = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
    response = requests.get(url)
    search_results = json.loads(response.text)
    if 'status_code' in search_results:
        response = requests.get(url_tv)
        tv_json = json.loads(response.text)
        log.debug("TMDB TV external IDs response keys: %s", [str(k) for k in tv_json.keys()])
        if 'status_code' not in tv_json:
            return tv_json['imdb_id']
        return None
    return search_results['external_ids']['imdb_id']


def tmdb_find(imdb_id):
    """
    basic function to return an object from TMDB from only the IMDB id
    """
    tmdb_api_key = cfg.arm_config['TMDB_API_KEY']
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={tmdb_api_key}&external_source=imdb_id"
    poster_size = "original"
    poster_base = f"https://image.tmdb.org/t/p/{poster_size}"
    response = requests.get(url)
    search_results = json.loads(response.text)
    if len(search_results['movie_results']) > 0:
        return_results = {'results': search_results['movie_results']}
        return_results['poster_url'] = f"{poster_base}{return_results['results'][0]['poster_path']}"
        return_results["Plot"] = return_results['results'][0]['overview']
        return_results['background_url'] = f"{poster_base}{return_results['results'][0]['backdrop_path']}"
        return_results['Type'] = "movie"
        return_results['imdbID'] = imdb_id
        return_results['Poster'] = return_results['poster_url']
        return_results['Year'] = re.sub(TMDB_YEAR_REGEX, "", return_results['results'][0]['release_date'])
        return_results['Title'] = return_results['results'][0]['title']
    else:
        return_results = {'results': search_results['tv_results']}
        return_results['poster_url'] = f"{poster_base}{return_results['results'][0]['poster_path']}"
        return_results["Plot"] = return_results['results'][0]['overview']
        return_results['background_url'] = f"{poster_base}{return_results['results'][0]['backdrop_path']}"
        return_results['imdbID'] = imdb_id
        return_results['Type'] = "series"
        return_results['Poster'] = return_results['poster_url']
        return_results['Year'] = re.sub(TMDB_YEAR_REGEX, "", return_results['results'][0]['first_air_date'])
        return_results['Title'] = return_results['results'][0]['name']
    return return_results


def tmdb_fetch_results(search_query, year, tmdb_api_key):
    """
    Main function for fetching movie results from TMDB
    """
    if year:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={search_query}&year={year}"
    else:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={search_query}"
    poster_size = "original"
    poster_base = f"https://image.tmdb.org/t/p/{poster_size}"
    response = requests.get(url)
    return_json = json.loads(response.text)
    return return_json, poster_base, response


def metadata_selector(func, query="", year="", imdb_id=""):
    """
    Used to switch between OMDB or TMDB as the metadata provider
    - TMDB returned queries are converted into the OMDB format
    """
    return_function = None
    if cfg.arm_config['METADATA_PROVIDER'].lower() == "tmdb":
        log.debug(f"provider tmdb - function: {func}")
        if func == "search":
            return_function = tmdb_search(str(query), str(year))
        elif func == "get_details":
            if query:
                log.debug("provider tmdb - using: get_tmdb_poster")
                return_function = get_tmdb_poster(str(query), str(year))
            elif imdb_id:
                log.debug("provider tmdb - using: tmdb_find")
                return_function = tmdb_find(imdb_id)
            log.debug("No title or imdb provided")

    elif cfg.arm_config['METADATA_PROVIDER'].lower() == "omdb":
        log.debug(f"provider omdb - function: {func}")
        if func == "search":
            return_function = call_omdb_api(str(query), str(year))
        elif func == "get_details":
            return_function = call_omdb_api(title=str(query), year=str(year), imdb_id=str(imdb_id), plot="full")
    else:
        log.debug("Unknown metadata selected")
    return return_function


def job_dupe_check(crc_id):
    """
    function for checking the database to look for jobs that have completed
    successfully with the same crc
    """
    if crc_id is None:
        return False, None
    jobs = Job.query.filter_by(crc_id=crc_id, status="success", hasnicetitle=True)
    return_results = {}
    i = 0
    for j in jobs:
        log.debug("job obj= " + str(j.get_d()))
        return_results[i] = {}
        for key, value in iter(j.get_d().items()):
            return_results[i][str(key)] = str(value)
        i += 1

    log.debug(return_results)
    log.debug("r len=" + str(len(return_results)))
    if jobs is not None and len(return_results) > 0:
        log.debug("jobs is none or len(r) - we have jobs")
        return True, return_results
    log.debug("jobs is none or len(r) is 0 - we have no jobs")
    return False, None
