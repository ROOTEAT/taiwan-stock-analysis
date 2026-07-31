from twstock_lab.changelog import CHANGELOG, CURRENT_VERSION, VERSION_PATTERN


def test_changelog_versions_are_valid_and_unique():
    versions = [entry.version for entry in CHANGELOG]
    assert versions
    assert len(versions) == len(set(versions))
    assert all(VERSION_PATTERN.fullmatch(version) for version in versions)


def test_current_version_is_newest_entry():
    assert CURRENT_VERSION == CHANGELOG[0].version


def test_release_notes_are_not_empty():
    assert all(entry.title.strip() and entry.changes for entry in CHANGELOG)
    assert all(change.strip() for entry in CHANGELOG for change in entry.changes)
