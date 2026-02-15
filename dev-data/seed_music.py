"""Seed music CD jobs into the ARM database."""
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("/home/arm/db/arm.db")
c = conn.cursor()

now = datetime.now()
VER = "2.8.0"

job_cols = (
    "arm_version", "crc_id", "logfile", "start_time", "stop_time",
    "job_length", "status", "no_of_titles",
    "title", "title_auto", "title_manual",
    "year", "year_auto", "year_manual",
    "video_type", "video_type_auto", "video_type_manual",
    "imdb_id", "imdb_id_auto", "imdb_id_manual",
    "poster_url", "poster_url_auto", "poster_url_manual",
    "devpath", "mountpoint", "hasnicetitle", "errors", "disctype",
    "label", "ejected", "updated", "pid", "pid_hash",
    "path", "stage", "is_iso", "manual_start", "manual_mode",
)
placeholders = ", ".join(["?"] * len(job_cols))
col_str = ", ".join(job_cols)

jobs = [
    # 11: Dark Side of the Moon — completed
    (VER, "m1a2b3c4d5e60011", "Dark_Side_of_the_Moon.log",
     (now - timedelta(days=5, hours=3)).isoformat(),
     (now - timedelta(days=5, hours=2, minutes=38)).isoformat(),
     "0:22:15", "success", 10,
     "Dark Side of the Moon", "Dark Side of the Moon", None,
     "1973", "1973", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr0", "/mnt/dev/sr0", 1, None, "music",
     "DARK_SIDE_OF_THE_MOON", 1, 0, 15100, 96100,
     "/home/arm/media/music/Dark Side of the Moon", "170000000011", 0, 0, 0),

    # 12: Rumours — completed
    (VER, "m2b3c4d5e6f70012", "Rumours.log",
     (now - timedelta(days=4, hours=1)).isoformat(),
     (now - timedelta(days=4, minutes=40)).isoformat(),
     "0:20:05", "success", 11,
     "Rumours", "Rumours", None,
     "1977", "1977", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr1", "/mnt/dev/sr1", 1, None, "music",
     "RUMOURS", 1, 0, 15200, 96200,
     "/home/arm/media/music/Rumours", "170000000012", 0, 0, 0),

    # 13: OK Computer — completed
    (VER, "m3c4d5e6f7a80013", "OK_Computer.log",
     (now - timedelta(days=2, hours=6)).isoformat(),
     (now - timedelta(days=2, hours=5, minutes=32)).isoformat(),
     "0:28:10", "success", 12,
     "OK Computer", "OK Computer", None,
     "1997", "1997", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr0", "/mnt/dev/sr0", 1, None, "music",
     "OK_COMPUTER", 1, 0, 15300, 96300,
     "/home/arm/media/music/OK Computer", "170000000013", 0, 0, 0),

    # 14: Kind of Blue — completed
    (VER, "m4d5e6f7a8b90014", "Kind_of_Blue.log",
     (now - timedelta(days=1, hours=8)).isoformat(),
     (now - timedelta(days=1, hours=7, minutes=42)).isoformat(),
     "0:18:30", "success", 5,
     "Kind of Blue", "Kind of Blue", None,
     "1959", "1959", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr0", "/mnt/dev/sr0", 1, None, "music",
     "KIND_OF_BLUE", 1, 0, 15400, 96400,
     "/home/arm/media/music/Kind of Blue", "170000000014", 0, 0, 0),

    # 15: Currently ripping a music CD
    (VER, "m5e6f7a8b9c00015", "Nevermind.log",
     (now - timedelta(minutes=8)).isoformat(), None,
     None, "ripping", 13,
     "Nevermind", "Nevermind", None,
     "1991", "1991", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr1", "/mnt/dev/sr1", 1, None, "music",
     "NEVERMIND", 0, 0, 15500, 96500,
     "/home/arm/media/music/Nevermind", "170000000015", 0, 0, 0),

    # 16: Failed music rip — unidentified
    (VER, "m6f7a8b9c0d10016", "music_cd.log",
     (now - timedelta(hours=20)).isoformat(),
     (now - timedelta(hours=19, minutes=55)).isoformat(),
     "0:05:02", "fail", 0,
     "not identified", "not identified", None,
     "0000", "0000", None,
     "unknown", "unknown", None,
     None, None, None,
     None, None, None,
     "/dev/sr0", "/mnt/dev/sr0", 0,
     "abcde: cdparanoia could not read disc — possible scratched or damaged media",
     "music",
     "AUDIO_CD", 1, 0, 15600, 96600,
     "/home/arm/media/music/not identified", "170000000016", 0, 0, 0),
]

for j in jobs:
    c.execute(f"INSERT INTO job ({col_str}) VALUES ({placeholders})", j)
print(f"Inserted {len(jobs)} music jobs (IDs 11-16)")

# Configs
for job_id in range(11, 17):
    c.execute(
        """INSERT INTO config (job_id, ARM_CHECK_UDF, GET_VIDEO_TITLE, SKIP_TRANSCODE,
           VIDEOTYPE, MINLENGTH, MAXLENGTH, MANUAL_WAIT, MANUAL_WAIT_TIME,
           TRANSCODE_PATH, RAW_PATH, COMPLETED_PATH, INSTALLPATH, LOGPATH, LOGLEVEL,
           DBFILE, RIPMETHOD, MAINFEATURE, DEST_EXT, NOTIFY_RIP, NOTIFY_TRANSCODE)
           VALUES (?,1,1,0,'auto','120','99999',1,120,
           '/home/arm/media/transcode','/home/arm/media/raw','/home/arm/media/completed',
           '/opt/arm','/home/arm/logs','DEBUG','/home/arm/db/arm.db','mkv',0,'mkv',1,1)""",
        (job_id,),
    )

# Tracks — music CDs have audio tracks with lengths in seconds
music_tracks = [
    # 11: Dark Side of the Moon
    (11, "01", 65, None, None, 0, "01-Speak_to_Me.flac", "01-Speak_to_Me.flac", "success"),
    (11, "02", 169, None, None, 0, "02-Breathe.flac", "02-Breathe.flac", "success"),
    (11, "03", 214, None, None, 0, "03-On_the_Run.flac", "03-On_the_Run.flac", "success"),
    (11, "04", 405, None, None, 0, "04-Time.flac", "04-Time.flac", "success"),
    (11, "05", 305, None, None, 0, "05-The_Great_Gig_in_the_Sky.flac", "05-The_Great_Gig_in_the_Sky.flac", "success"),
    (11, "06", 382, None, None, 0, "06-Money.flac", "06-Money.flac", "success"),
    (11, "07", 471, None, None, 0, "07-Us_and_Them.flac", "07-Us_and_Them.flac", "success"),
    (11, "08", 180, None, None, 0, "08-Any_Colour_You_Like.flac", "08-Any_Colour_You_Like.flac", "success"),
    (11, "09", 228, None, None, 0, "09-Brain_Damage.flac", "09-Brain_Damage.flac", "success"),
    (11, "10", 126, None, None, 0, "10-Eclipse.flac", "10-Eclipse.flac", "success"),
    # 12: Rumours
    (12, "01", 155, None, None, 0, "01-Second_Hand_News.flac", "01-Second_Hand_News.flac", "success"),
    (12, "02", 238, None, None, 0, "02-Dreams.flac", "02-Dreams.flac", "success"),
    (12, "03", 195, None, None, 0, "03-Never_Going_Back_Again.flac", "03-Never_Going_Back_Again.flac", "success"),
    (12, "04", 222, None, None, 0, "04-Dont_Stop.flac", "04-Dont_Stop.flac", "success"),
    (12, "05", 219, None, None, 0, "05-Go_Your_Own_Way.flac", "05-Go_Your_Own_Way.flac", "success"),
    (12, "06", 258, None, None, 0, "06-Songbird.flac", "06-Songbird.flac", "success"),
    (12, "07", 271, None, None, 0, "07-The_Chain.flac", "07-The_Chain.flac", "success"),
    (12, "08", 230, None, None, 0, "08-You_Make_Loving_Fun.flac", "08-You_Make_Loving_Fun.flac", "success"),
    (12, "09", 185, None, None, 0, "09-I_Dont_Want_to_Know.flac", "09-I_Dont_Want_to_Know.flac", "success"),
    (12, "10", 211, None, None, 0, "10-Oh_Daddy.flac", "10-Oh_Daddy.flac", "success"),
    (12, "11", 272, None, None, 0, "11-Gold_Dust_Woman.flac", "11-Gold_Dust_Woman.flac", "success"),
    # 13: OK Computer
    (13, "01", 284, None, None, 0, "01-Airbag.flac", "01-Airbag.flac", "success"),
    (13, "02", 369, None, None, 0, "02-Paranoid_Android.flac", "02-Paranoid_Android.flac", "success"),
    (13, "03", 293, None, None, 0, "03-Subterranean_Homesick_Alien.flac",
     "03-Subterranean_Homesick_Alien.flac", "success"),
    (13, "04", 290, None, None, 0, "04-Exit_Music.flac", "04-Exit_Music.flac", "success"),
    (13, "05", 247, None, None, 0, "05-Let_Down.flac", "05-Let_Down.flac", "success"),
    (13, "06", 264, None, None, 0, "06-Karma_Police.flac", "06-Karma_Police.flac", "success"),
    (13, "07", 79, None, None, 0, "07-Fitter_Happier.flac", "07-Fitter_Happier.flac", "success"),
    (13, "08", 229, None, None, 0, "08-Electioneering.flac", "08-Electioneering.flac", "success"),
    (13, "09", 285, None, None, 0, "09-Climbing_Up_the_Walls.flac", "09-Climbing_Up_the_Walls.flac", "success"),
    (13, "10", 263, None, None, 0, "10-No_Surprises.flac", "10-No_Surprises.flac", "success"),
    (13, "11", 318, None, None, 0, "11-Lucky.flac", "11-Lucky.flac", "success"),
    (13, "12", 338, None, None, 0, "12-The_Tourist.flac", "12-The_Tourist.flac", "success"),
    # 14: Kind of Blue
    (14, "01", 561, None, None, 0, "01-So_What.flac", "01-So_What.flac", "success"),
    (14, "02", 579, None, None, 0, "02-Freddie_Freeloader.flac", "02-Freddie_Freeloader.flac", "success"),
    (14, "03", 690, None, None, 0, "03-Blue_in_Green.flac", "03-Blue_in_Green.flac", "success"),
    (14, "04", 693, None, None, 0, "04-All_Blues.flac", "04-All_Blues.flac", "success"),
    (14, "05", 567, None, None, 0, "05-Flamenco_Sketches.flac", "05-Flamenco_Sketches.flac", "success"),
    # 15: Nevermind (ripping — partial)
    (15, "01", 301, None, None, 0, "01-Smells_Like_Teen_Spirit.flac", "01-Smells_Like_Teen_Spirit.flac", "success"),
    (15, "02", 216, None, None, 0, "02-In_Bloom.flac", "02-In_Bloom.flac", "success"),
    (15, "03", 206, None, None, 0, "03-Come_as_You_Are.flac", "03-Come_as_You_Are.flac", "success"),
    (15, "04", 176, None, None, 0, "04-Breed.flac", "04-Breed.flac", "success"),
    (15, "05", 249, None, None, 0, "05-Lithium.flac", "05-Lithium.flac", "ripping"),
    (15, "06", 157, None, None, 0, "06-Polly.flac", None, None),
    (15, "07", 211, None, None, 0, "07-Territorial_Pissings.flac", None, None),
    (15, "08", 242, None, None, 0, "08-Drain_You.flac", None, None),
    (15, "09", 218, None, None, 0, "09-Lounge_Act.flac", None, None),
    (15, "10", 156, None, None, 0, "10-Stay_Away.flac", None, None),
    (15, "11", 204, None, None, 0, "11-On_a_Plain.flac", None, None),
    (15, "12", 225, None, None, 0, "12-Something_in_the_Way.flac", None, None),
    (15, "13", 403, None, None, 0, "13-Endless_Nameless.flac", None, None),
]

for t in music_tracks:
    ripped = 1 if t[8] == "success" else 0
    c.execute(
        """INSERT INTO track (job_id, track_number, length, aspect_ratio, fps,
           main_feature, basename, filename, ripped, status, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], ripped, t[8], "flac"),
    )
print(f"Inserted {len(music_tracks)} tracks")

# Notifications
notifs = [
    ("Job: 11 completed", "Dark Side of the Moon (1973) ripped successfully",
     now - timedelta(days=5, hours=2, minutes=38)),
    ("Job: 12 completed", "Rumours (1977) ripped successfully",
     now - timedelta(days=4, minutes=40)),
    ("Job: 13 completed", "OK Computer (1997) ripped successfully",
     now - timedelta(days=2, hours=5, minutes=32)),
    ("Job: 14 completed", "Kind of Blue (1959) ripped successfully",
     now - timedelta(days=1, hours=7, minutes=42)),
    ("Job: 15 started", "Nevermind (1991) rip started on /dev/sr1",
     now - timedelta(minutes=8)),
    ("Job: 16 failed", "Audio CD: cdparanoia could not read disc",
     now - timedelta(hours=19, minutes=55)),
]
for title, msg, t in notifs:
    c.execute(
        "INSERT INTO notifications (seen, trigger_time, title, message, cleared) VALUES (0,?,?,?,0)",
        (t.isoformat(), title, msg),
    )
print(f"Inserted {len(notifs)} notifications")

conn.commit()
conn.close()
print("Done!")
