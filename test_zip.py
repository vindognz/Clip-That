import io
import zipfile

from export import build_zip, safe_filename


# safe_filename

def test_normal_username_is_unchanged():
    assert safe_filename("c_sharp_minor") == "c_sharp_minor"

def test_path_tricks_are_neutralised():
    devious = ["a/b", "../evil", "..\\evil", "/etc/passwd", "C:\\Windows\\x", "a/../b"]
    for name in devious:
        out = safe_filename(name)
        assert "/" not in out, name
        assert "\\" not in out, name
        assert ".." not in out, name

def test_empty_name_falls_back_to_something():
    assert safe_filename("") != ""

def test_name_of_only_bad_characters_is_still_usable():
    out = safe_filename("///")
    assert out != ""
    assert "/" not in out

def test_emoji_name_is_still_usable():
    out = safe_filename("🔥🔥")
    assert out != ""
    assert "/" not in out


# build_zip

def open_zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))

def test_zip_returns_bytes_that_open_as_a_zip():
    result = build_zip({"a.mp3": b"hello"})
    assert isinstance(result, bytes)
    assert zipfile.is_zipfile(io.BytesIO(result))

def test_zip_contains_the_files_we_gave_it():
    files = {"alice.mp3": b"aaa", "bob.mp3": b"bbb"}
    zf = open_zip(build_zip(files))
    assert sorted(zf.namelist()) == ["alice.mp3", "bob.mp3"]

def test_file_bytes_round_trip():
    files = {"alice.mp3": b"\x00\x01\x02" * 1000, "bob.mp3": b"\xff" * 500}
    zf = open_zip(build_zip(files))
    for name, data in files.items():
        assert zf.read(name) == data

def test_zip_is_stored_not_compressed():
    zf = open_zip(build_zip({"a.mp3": b"x" * 100}))
    assert zf.getinfo("a.mp3").compress_type == zipfile.ZIP_STORED

def test_empty_zip_is_still_a_valid_zip():
    zf = open_zip(build_zip({}))
    assert zf.namelist() == []