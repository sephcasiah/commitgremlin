"""
Tests for ActivityState — no file system or git required.
"""

import time
import pytest


def make_state():
    from commitgremlin.tracker import ActivityState
    return ActivityState()


def test_no_activity_is_zero_seconds():
    s = make_state()
    assert s.active_seconds == 0


def test_single_session_accumulates():
    s = make_state()
    s._session_start = time.monotonic() - 5
    s._last_event = time.monotonic()
    s.close_session()
    assert s.active_seconds >= 5


def test_close_session_is_idempotent():
    s = make_state()
    s._session_start = time.monotonic() - 3
    s._last_event = time.monotonic()
    s.close_session()
    first = s.active_seconds
    s.close_session()
    assert s.active_seconds == first


def test_active_time_str_format():
    s = make_state()
    s._accumulated_seconds = 3661  # 1h 01m 01s
    assert s.active_time_str == "1h 01m 01s"


def test_to_dict_keys():
    s = make_state()
    d = s.to_dict()
    for key in ("date", "files_modified", "projects", "builds", "active_seconds", "active_time"):
        assert key in d


def test_files_and_projects_are_sorted_lists():
    s = make_state()
    s.files_modified = {"z_file.c", "a_file.c"}
    s.projects = {"zebra", "apple"}
    d = s.to_dict()
    assert d["files_modified"] == sorted(d["files_modified"])
    assert d["projects"] == sorted(d["projects"])
