"""Tests for config utilities (arm/config/config_utils.py)."""


class TestArmYamlTestBool:
    """Test arm_yaml_test_bool() YAML value formatting."""

    def test_true_value(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("SKIP_TRANSCODE", "True")
        assert result == "SKIP_TRANSCODE: true\n"

    def test_false_value(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("SKIP_TRANSCODE", "False")
        assert result == "SKIP_TRANSCODE: false\n"

    def test_case_insensitive_true(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("NOTIFY_RIP", "TRUE")
        assert result == "NOTIFY_RIP: true\n"

    def test_case_insensitive_false(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("NOTIFY_RIP", "FALSE")
        assert result == "NOTIFY_RIP: false\n"

    def test_webserver_ip_no_quotes(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("WEBSERVER_IP", "192.168.1.100")
        assert result == "WEBSERVER_IP: 192.168.1.100\n"

    def test_string_value_quoted(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("RAW_PATH", "/home/arm/media/raw")
        assert result == 'RAW_PATH: "/home/arm/media/raw"\n'

    def test_string_with_quotes_escaped(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("TITLE", 'He said "hello"')
        assert '\\"' in result
        assert "TITLE:" in result

    def test_empty_string(self):
        from arm.config.config_utils import arm_yaml_test_bool
        result = arm_yaml_test_bool("BASH_SCRIPT", "")
        assert result == 'BASH_SCRIPT: ""\n'


def _full_comments():
    """Build a complete ARM_CFG_GROUPS dict (all keys required at call time)."""
    return {
        'ARM_CFG_GROUPS': {
            'DIR_SETUP': '# Directory Setup',
            'WEB_SERVER': '# Web Server',
            'FILE_PERMS': '# File Permissions',
            'MAKE_MKV': '# MakeMKV',
            'HANDBRAKE': '# HandBrake',
            'EMBY': '# Emby',
            'EMBY_ADDITIONAL': '# Emby Additional',
            'NOTIFY_PERMS': '# Notifications',
            'APPRISE': '# Apprise',
        }
    }


class TestArmYamlCheckGroups:
    """Test arm_yaml_check_groups() comment section insertion."""

    def test_known_key_returns_comment(self):
        from arm.config.config_utils import arm_yaml_check_groups
        result = arm_yaml_check_groups(_full_comments(), 'COMPLETED_PATH')
        assert '# Directory Setup' in result

    def test_unknown_key_returns_empty(self):
        from arm.config.config_utils import arm_yaml_check_groups
        result = arm_yaml_check_groups(_full_comments(), 'UNKNOWN_KEY')
        assert result == ""

    def test_webserver_ip_returns_web_server(self):
        from arm.config.config_utils import arm_yaml_check_groups
        result = arm_yaml_check_groups(_full_comments(), 'WEBSERVER_IP')
        assert '# Web Server' in result

    def test_notify_rip_returns_notify(self):
        from arm.config.config_utils import arm_yaml_check_groups
        result = arm_yaml_check_groups(_full_comments(), 'NOTIFY_RIP')
        assert '# Notifications' in result
