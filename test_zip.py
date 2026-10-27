import io
import zipfile

from export import build_zip, safe_filename, build_clip


# safe_filename

def test_normal_username_is_unchanged():
    assert safe_filename("c_sharp_minor") == "c_sharp_minor"

def test_dots_preserved():
    assert safe_filename("c.sharp_minor") == "c.sharp_minor"

def test_junk_name():
    # Discord usernames cannot contain these, but safe_filename should safeguard anyways
    assert safe_filename("a/b:c*d_e.f$g") == "a_b_c_d_e.f_g"

def test_no_dot_nasties():
    assert safe_filename("a.") == "a"
    assert safe_filename(".a") == "a"
    assert safe_filename("a..a") == "a_a"

def test_empty_name_falls_back_to_something():
    assert safe_filename("") != ""



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



# build clip

def test_clip_with_no_tracks():
    assert build_clip({}, {1: "test"}) is None

def test_returns_valid_mp3_and_zip():
    tracks = {
        1: bytes(192000),
        2: bytes(192000)
    }

    names = {
        1: "A",
        2: "B"
    }

    mix, zip_bytes = build_clip(tracks, names)

    assert mix[0] == 0xFF
    assert zipfile.is_zipfile(io.BytesIO(zip_bytes))

def test_zip_contains_mp3s_for_each_user():
    tracks = {
        1: bytes(192000),
        2: bytes(192000),
    }

    names = {
        1: "A",
        2: "B",
        3: "im_a_ghost"
    }

    _, zip_bytes = build_clip(tracks, names)

    zf = open_zip(zip_bytes)
    assert zf.namelist() == ["A.mp3", "B.mp3"]

    assert zf.read("A.mp3")[0] == 0xFF
    assert zf.read("B.mp3")[0] == 0xFF

def test_user_missing_from_names_gets_user_id_dot_mp3():
    tracks = {
        1: bytes(192000),
        2: bytes(192000)
    }

    names = {
        1: "A",
    }

    _, zip_bytes = build_clip(tracks, names)

    zf = open_zip(zip_bytes)
    assert zf.namelist() == ["A.mp3", "2.mp3"]

def test_dots_survive_in_filename():
    tracks = {
        1: bytes(192000),
        2: bytes(192000)
    }

    names = {
        1: "A",
        2: "my.name.is.bob"
    }

    _, zip_bytes = build_clip(tracks, names)

    zf = open_zip(zip_bytes)
    assert zf.namelist() == ["A.mp3", "my.name.is.bob.mp3"]