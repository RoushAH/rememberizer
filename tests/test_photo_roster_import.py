"""Tests for building a domain from a roster CSV plus a folder or zip of photos."""

import io
import os
import zipfile

import pytest

from models import Domain, Fact
from services.image_service import image_reference
from services.photo_roster_service import (
    build_photo_facts,
    collect_photo_files,
    collect_zip_photos,
    decode_csv,
    format_import_report,
    normalise_field_name,
    parse_roster_csv,
    photo_key,
    resolve_included_headers,
)

# Reuse the minimal valid image files from the image-field tests.
from tests.test_image_fields import GIF_BYTES, JPEG_BYTES, PNG_BYTES, upload

ROSTER_CSV = (
    "ManagementSystemID,Surname,Forename,YearGroup,TutorGroup\n"
    "10482,Wright,Alex,Year 9,9B\n"
    "10483,Okafor,Chidi,Year 9,9B\n"
    "10484,Silva,Ana,Year 9,9B\n"
    "10485,Novak,Petr,Year 9,9C\n"
)

ROSTER_IDS = ["10482", "10483", "10484", "10485"]


@pytest.fixture(autouse=True)
def isolate_uploads(app, tmp_path):
    """Keep uploads out of the real static folder (the app is a singleton)."""
    original = app.config.get("UPLOAD_FOLDER")
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    yield tmp_path / "uploads"
    app.config["UPLOAD_FOLDER"] = original


def photo_files(ids, content=JPEG_BYTES, extension=".jpg"):
    """Build one uploaded photo per ID, as a folder picker would submit them."""
    return [upload(content, f"photos/{student_id}{extension}") for student_id in ids]


def photo_zip(ids, content=JPEG_BYTES, extension=".jpg", extra=None):
    """Build a zip of photos named after the given IDs."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for student_id in ids:
            archive.writestr(f"photos/{student_id}{extension}", content)
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    buffer.seek(0)
    return upload(buffer.getvalue(), "isams_photos.zip")


# ============================================================================
# FIELD NAMES
# ============================================================================


def test_normalise_field_name_splits_camel_case():
    """MIS headers are CamelCase; questions need readable words."""
    assert normalise_field_name("YearGroup") == "year_group"
    assert normalise_field_name("DateOfBirth") == "date_of_birth"
    assert normalise_field_name("ManagementSystemID") == "management_system_id"


def test_normalise_field_name_tidies_punctuation_and_case():
    """Spaces, hyphens and stray punctuation all collapse to underscores."""
    assert normalise_field_name("Tutor Group") == "tutor_group"
    assert normalise_field_name("Form-Room") == "form_room"
    assert normalise_field_name("  surname  ") == "surname"
    assert normalise_field_name("Pupil (preferred)") == "pupil_preferred"


def test_normalise_field_name_handles_unusable_headers():
    """A header with nothing usable in it normalises to empty."""
    assert normalise_field_name("") == ""
    assert normalise_field_name("###") == ""
    assert normalise_field_name(None) == ""


# ============================================================================
# PHOTO MATCHING
# ============================================================================


def test_photo_key_ignores_path_extension_and_case():
    """The CSV holds a bare ID; files arrive with paths and extensions."""
    assert photo_key("photos/10482.jpg") == "10482"
    assert photo_key("photos\\10482.JPG") == "10482"
    assert photo_key("10482.jpeg") == "10482"
    assert photo_key("Alex Wright.png") == "alex wright"


def test_collect_photo_files_indexes_by_key():
    """Photos are looked up by the value their filename matches."""
    photos = collect_photo_files(photo_files(["10482", "10483"]))

    assert sorted(photos) == ["10482", "10483"]


def test_collect_photo_files_ignores_non_photos_and_dotfiles():
    """A folder picker submits everything in the folder, not just images."""
    photos = collect_photo_files(
        [
            upload(JPEG_BYTES, "photos/10482.jpg"),
            upload(b"id,name\n", "photos/roster.csv"),
            upload(b"anything", "photos/Thumbs.db"),
            upload(JPEG_BYTES, "photos/.DS_Store"),
            upload(JPEG_BYTES, "photos/._10483.jpg"),
            upload(b"", ""),
        ]
    )

    assert sorted(photos) == ["10482"]


def test_collect_photo_files_keeps_first_of_duplicate_keys():
    """Two files with one key is ambiguous; the first one is used."""
    first = upload(JPEG_BYTES, "10482.jpg")
    second = upload(PNG_BYTES, "10482.png")

    photos = collect_photo_files([first, second])

    assert photos["10482"] is first


# ============================================================================
# ZIP INPUT
# ============================================================================


def test_collect_zip_photos_reads_nested_entries():
    """Photos are found wherever they sit inside the archive."""
    photos = collect_zip_photos(photo_zip(ROSTER_IDS))

    assert sorted(photos) == ROSTER_IDS


def test_collect_zip_photos_ignores_mac_metadata_and_other_files():
    """The junk a Mac adds to a zip is skipped, not treated as a photo."""
    photos = collect_zip_photos(
        photo_zip(
            ["10482"],
            extra={
                "__MACOSX/._10483.jpg": b"junk",
                "photos/readme.txt": b"hello",
                "photos/sub/": b"",
            },
        )
    )

    assert sorted(photos) == ["10482"]


def test_collect_zip_photos_rejects_a_non_zip():
    """A file that is not a zip is called out rather than crashing."""
    with pytest.raises(ValueError, match="not a readable zip file"):
        collect_zip_photos(upload(b"definitely not a zip", "photos.zip"))


def test_collect_zip_photos_rejects_oversized_entry(monkeypatch):
    """An entry over the per-image cap is refused before it is expanded."""
    monkeypatch.setattr("services.photo_roster_service.MAX_IMAGE_BYTES", 10)

    with pytest.raises(ValueError, match="the limit is"):
        collect_zip_photos(photo_zip(["10482"], content=JPEG_BYTES))


def test_collect_zip_photos_rejects_oversized_total(monkeypatch):
    """A zip that expands past the total cap is refused (zip-bomb guard)."""
    monkeypatch.setattr("services.photo_roster_service.MAX_ZIP_TOTAL_BYTES", 10)

    with pytest.raises(ValueError, match="expands to more than"):
        collect_zip_photos(photo_zip(ROSTER_IDS))


def test_collect_zip_photos_rejects_too_many_entries(monkeypatch):
    """An archive with implausibly many entries is refused."""
    monkeypatch.setattr("services.photo_roster_service.MAX_ZIP_ENTRIES", 2)

    with pytest.raises(ValueError, match="the limit is 2"):
        collect_zip_photos(photo_zip(ROSTER_IDS))


# ============================================================================
# CSV PARSING
# ============================================================================


def test_decode_csv_accepts_utf8_with_bom():
    """Excel writes a BOM; it must not end up inside the first header."""
    text = decode_csv(b"\xef\xbb\xbfID,Surname\n10482,Wright\n")

    assert text.startswith("ID,Surname")


def test_decode_csv_accepts_plain_utf8():
    """A BOM-less UTF-8 export reads too."""
    text = decode_csv("ID,Surname\n10482,Wright\n".encode("utf-8"))

    assert text.startswith("ID,Surname")


def test_decode_csv_falls_back_to_windows_encoding():
    """A cp1252 export still reads rather than dead-ending the teacher."""
    text = decode_csv("ID,Surname\n10482,Ang\xe9lique\n".encode("cp1252"))

    assert "Ang\xe9lique" in text


def test_parse_roster_csv_strips_headers():
    """Stray spaces around headers do not become part of field names."""
    headers, rows = parse_roster_csv(" ID , Surname \n10482,Wright\n")

    assert headers == ["ID", "Surname"]
    assert rows == [{"ID": "10482", "Surname": "Wright"}]


def test_parse_roster_csv_rejects_empty_file():
    """An empty upload gets a clear message, not an index error."""
    with pytest.raises(ValueError, match="needs a header row"):
        parse_roster_csv("")


def test_parse_roster_csv_rejects_single_column():
    """One column gives nothing to quiz against the photo."""
    with pytest.raises(ValueError, match="at least two columns"):
        parse_roster_csv("ID\n10482\n")


# ============================================================================
# COLUMN SELECTION
# ============================================================================


def test_resolve_included_headers_defaults_to_every_detail_column():
    """The first column is the photo key and is never a field."""
    headers = ["ID", "Surname", "Forename"]

    assert resolve_included_headers(headers) == ["Surname", "Forename"]


def test_resolve_included_headers_keeps_csv_order():
    """Chosen columns come out in CSV order, whatever order they were typed."""
    headers = ["ID", "Surname", "Forename", "YearGroup"]

    included = resolve_included_headers(headers, ["YearGroup", "Surname"])

    assert included == ["Surname", "YearGroup"]


def test_resolve_included_headers_matches_loosely():
    """A teacher may type the tidied field name or a different case."""
    headers = ["ID", "Surname", "YearGroup"]

    assert resolve_included_headers(headers, ["surname", "year_group"]) == [
        "Surname",
        "YearGroup",
    ]


def test_resolve_included_headers_rejects_unknown_column():
    """A typo names the available columns instead of silently dropping it."""
    headers = ["ID", "Surname", "Forename"]

    with pytest.raises(ValueError, match="no column 'Nickname'"):
        resolve_included_headers(headers, ["Nickname"])


def test_resolve_included_headers_ignores_blank_entries():
    """Trailing commas in the form field are not columns."""
    headers = ["ID", "Surname", "Forename"]

    assert resolve_included_headers(headers, ["Surname", "", "  "]) == ["Surname"]


def test_resolve_included_headers_rejects_nothing_chosen():
    """An entry of only blanks is refused rather than quizzing nothing."""
    with pytest.raises(ValueError, match="at least one column"):
        resolve_included_headers(["ID", "Surname"], ["", " "])


# ============================================================================
# FACT ASSEMBLY
# ============================================================================


def test_build_photo_facts_replaces_the_id_column_with_the_photo(app):
    """Each row becomes photo + details; the opaque ID is not a field."""
    with app.app_context():
        result = build_photo_facts(
            ROSTER_CSV, collect_photo_files(photo_files(ROSTER_IDS))
        )

    assert result["field_names"] == [
        "photo",
        "surname",
        "forename",
        "year_group",
        "tutor_group",
    ]
    assert result["key_column"] == "ManagementSystemID"
    assert len(result["facts_data"]) == 4

    alex = next(f for f in result["facts_data"] if f["forename"] == "Alex")
    assert alex["surname"] == "Wright"
    assert alex["year_group"] == "Year 9"
    assert alex["photo"].startswith("img:uploads/")
    assert "10482" not in alex["photo"]
    assert "management_system_id" not in alex


def test_build_photo_facts_stores_only_matched_photos(app, isolate_uploads):
    """A gallery wider than the roster does not drag extra files onto disk."""
    gallery = collect_photo_files(photo_files(ROSTER_IDS + ["99999", "99998"]))

    with app.app_context():
        result = build_photo_facts(ROSTER_CSV, gallery)

    assert len(os.listdir(isolate_uploads)) == 4
    assert result["unused_photos"] == ["99998", "99999"]


def test_build_photo_facts_skips_rows_without_a_photo(app):
    """A roster covering students with no photo still imports."""
    csv_content = ROSTER_CSV + "10486,Haddad,Nour,Year 9,9C\n"

    with app.app_context():
        result = build_photo_facts(
            csv_content, collect_photo_files(photo_files(ROSTER_IDS))
        )

    assert result["skipped_rows"] == ["10486"]
    assert len(result["facts_data"]) == 4


def test_build_photo_facts_skips_rows_with_a_blank_key(app):
    """A blank ID cell is counted, not matched against a blank filename."""
    csv_content = ROSTER_CSV + ",Blank,Row,Year 9,9C\n"

    with app.app_context():
        result = build_photo_facts(
            csv_content, collect_photo_files(photo_files(ROSTER_IDS))
        )

    assert result["blank_rows"] == 1
    assert len(result["facts_data"]) == 4


def test_build_photo_facts_matches_case_insensitively(app):
    """The export's casing does not have to match the filenames'."""
    csv_content = "ID,Surname\nAB12,Wright\nAB13,Okafor\nAB14,Silva\nAB15,Novak\n"
    photos = collect_photo_files(photo_files(["ab12", "ab13", "ab14", "ab15"]))

    with app.app_context():
        result = build_photo_facts(csv_content, photos)

    assert len(result["facts_data"]) == 4


def test_build_photo_facts_stores_a_shared_photo_once(app, isolate_uploads):
    """Two rows on one ID reuse the stored file rather than duplicating it."""
    csv_content = (
        "ID,Subject\n"
        "10482,Maths\n"
        "10482,English\n"
        "10483,Maths\n"
        "10484,Maths\n"
        "10485,Maths\n"
    )

    with app.app_context():
        result = build_photo_facts(
            csv_content, collect_photo_files(photo_files(ROSTER_IDS))
        )

    assert len(result["facts_data"]) == 5
    assert len(os.listdir(isolate_uploads)) == 4
    assert len(result["image_values"]) == 4


def test_build_photo_facts_honours_chosen_columns(app):
    """Columns nobody should be quizzed on can be left out."""
    with app.app_context():
        result = build_photo_facts(
            ROSTER_CSV,
            collect_photo_files(photo_files(ROSTER_IDS)),
            include_columns=["Surname"],
        )

    assert result["field_names"] == ["photo", "surname"]
    assert set(result["facts_data"][0]) == {"photo", "surname"}


def test_build_photo_facts_accepts_a_custom_photo_field(app):
    """The photo field name is what questions will call the picture."""
    with app.app_context():
        result = build_photo_facts(
            ROSTER_CSV,
            collect_photo_files(photo_files(ROSTER_IDS)),
            photo_field="Face Shot",
        )

    assert result["field_names"][0] == "face_shot"


def test_build_photo_facts_falls_back_to_the_default_photo_field(app):
    """An empty or unusable photo field name uses the default."""
    with app.app_context():
        result = build_photo_facts(
            ROSTER_CSV, collect_photo_files(photo_files(ROSTER_IDS)), photo_field="  "
        )

    assert result["field_names"][0] == "photo"


def test_build_photo_facts_accepts_every_image_type(app):
    """Photos are validated by content, so any accepted format works."""
    photos = collect_photo_files(
        [
            upload(JPEG_BYTES, "10482.jpg"),
            upload(PNG_BYTES, "10483.png"),
            upload(GIF_BYTES, "10484.gif"),
            upload(JPEG_BYTES, "10485.jpeg"),
        ]
    )

    with app.app_context():
        result = build_photo_facts(ROSTER_CSV, photos)

    stored = sorted(image_reference(v).split(".")[-1] for v in result["image_values"])
    assert stored == ["gif", "jpeg", "jpeg", "png"]


def test_build_photo_facts_rejects_too_few_matches(app, isolate_uploads):
    """Under four matched rows there is no multiple choice to build."""
    photos = collect_photo_files(photo_files(["10482", "10483"]))

    with app.app_context():
        with pytest.raises(ValueError, match="Only 2 row"):
            build_photo_facts(ROSTER_CSV, photos)

    # The two photos that did store were cleaned up again
    assert not os.path.exists(isolate_uploads) or os.listdir(isolate_uploads) == []


def test_build_photo_facts_cleans_up_when_a_photo_is_not_an_image(app, isolate_uploads):
    """A file that only looks like a photo fails the import and leaves nothing."""
    photos = collect_photo_files(
        photo_files(["10482", "10483", "10484"])
        + [upload(b"<script>alert(1)</script>", "10485.jpg")]
    )

    with app.app_context():
        with pytest.raises(ValueError, match="not a recognised image file"):
            build_photo_facts(ROSTER_CSV, photos)

    assert not os.path.exists(isolate_uploads) or os.listdir(isolate_uploads) == []


def test_build_photo_facts_rejects_colliding_field_names(app):
    """Two headers tidying down to one field name is an error, not a silent loss."""
    csv_content = (
        "ID,YearGroup,Year Group\n"
        "10482,Year 9,9\n"
        "10483,Year 9,9\n"
        "10484,Year 9,9\n"
        "10485,Year 9,9\n"
    )

    with app.app_context():
        with pytest.raises(ValueError, match="would both become the field"):
            build_photo_facts(csv_content, collect_photo_files(photo_files(ROSTER_IDS)))


def test_build_photo_facts_rejects_a_column_clashing_with_the_photo_field(app):
    """A 'photo' column cannot quietly overwrite the photo itself."""
    csv_content = "ID,Photo\n10482,x\n10483,x\n10484,x\n10485,x\n"

    with app.app_context():
        with pytest.raises(ValueError, match="the photo would both become"):
            build_photo_facts(csv_content, collect_photo_files(photo_files(ROSTER_IDS)))


def test_build_photo_facts_rejects_an_unnameable_column(app):
    """A header with no usable characters is refused."""
    csv_content = "ID,###\n10482,x\n10483,x\n10484,x\n10485,x\n"

    with app.app_context():
        with pytest.raises(ValueError, match="no usable name"):
            build_photo_facts(csv_content, collect_photo_files(photo_files(ROSTER_IDS)))


# ============================================================================
# REPORTING
# ============================================================================


def test_format_import_report_is_silent_on_a_clean_import():
    """Nothing to say when every row matched and every photo was used."""
    result = {
        "skipped_rows": [],
        "blank_rows": 0,
        "unused_photos": [],
        "key_column": "ID",
    }

    assert format_import_report(result) == ""


def test_format_import_report_names_what_was_left_out():
    """The teacher is told which rows and photos did not make it in."""
    result = {
        "skipped_rows": ["10486", "10487"],
        "blank_rows": 1,
        "unused_photos": ["99999"],
        "key_column": "ManagementSystemID",
    }

    report = format_import_report(result)

    assert "2 row(s) skipped with no matching photo: 10486, 10487." in report
    assert "1 row(s) skipped with a blank 'ManagementSystemID'." in report
    assert "1 photo(s) matched no row: 99999." in report


def test_format_import_report_summarises_a_long_list():
    """A big export does not produce an unreadable wall of IDs."""
    result = {
        "skipped_rows": [str(10000 + i) for i in range(25)],
        "blank_rows": 0,
        "unused_photos": [],
        "key_column": "ID",
    }

    report = format_import_report(result)

    assert "10009 and 15 more" in report


# ============================================================================
# THE ROUTE
# ============================================================================


def post_roster(client, **overrides):
    """POST the photo roster form with sensible defaults (None drops a field)."""
    data = {
        "domain_name": "9B Faces",
        "csv_file": upload(ROSTER_CSV.encode(), "roster.csv"),
        "photo_files": photo_files(ROSTER_IDS),
    }
    data.update(overrides)
    data = {key: value for key, value in data.items() if value is not None}

    return client.post(
        "/teacher/domains/import-photos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_route_creates_a_domain_from_a_folder_of_photos(
    app, authenticated_teacher, isolate_uploads
):
    """The happy path: CSV plus folder in, quizzable photo domain out."""
    response = post_roster(authenticated_teacher)

    assert response.status_code == 200
    assert "created with 4 photo facts" in response.data.decode()

    with app.app_context():
        domain = Domain.query.filter_by(name="9B Faces").first()
        assert domain is not None
        assert domain.get_field_names()[0] == "photo"
        assert domain.is_published is False

        facts = Fact.query.filter_by(domain_id=domain.id).all()
        assert len(facts) == 4

        surnames = sorted(fact.get_fact_data()["surname"] for fact in facts)
        assert surnames == ["Novak", "Okafor", "Silva", "Wright"]

        for fact in facts:
            assert fact.get_fact_data()["photo"].startswith("img:uploads/")

    assert len(os.listdir(isolate_uploads)) == 4


def test_route_creates_a_domain_from_a_zip(app, authenticated_teacher):
    """A zip straight out of the MIS works as well as a folder."""
    response = post_roster(
        authenticated_teacher, photo_files=[], photo_zip=photo_zip(ROSTER_IDS)
    )

    assert response.status_code == 200

    with app.app_context():
        domain = Domain.query.filter_by(name="9B Faces").first()
        assert domain is not None
        assert Fact.query.filter_by(domain_id=domain.id).count() == 4


def test_route_reports_rows_and_photos_left_out(app, authenticated_teacher):
    """The flash message says what did not make it into the domain."""
    csv_content = ROSTER_CSV + "10486,Haddad,Nour,Year 9,9C\n"

    response = post_roster(
        authenticated_teacher,
        csv_file=upload(csv_content.encode(), "roster.csv"),
        photo_files=photo_files(ROSTER_IDS + ["99999"]),
    )

    body = response.data.decode()
    assert "1 row(s) skipped with no matching photo: 10486." in body
    assert "1 photo(s) matched no row: 99999." in body


def test_route_narrows_fields_to_the_chosen_columns(app, authenticated_teacher):
    """The columns box keeps sensitive columns out of the domain."""
    post_roster(authenticated_teacher, include_columns="Surname, Forename")

    with app.app_context():
        domain = Domain.query.filter_by(name="9B Faces").first()
        assert domain.get_field_names() == ["photo", "surname", "forename"]


def test_route_requires_a_csv_file(app, authenticated_teacher):
    """Submitting without a CSV says so instead of erroring."""
    response = post_roster(authenticated_teacher, csv_file=None)

    assert "No CSV file selected" in response.data.decode()

    with app.app_context():
        assert Domain.query.filter_by(name="9B Faces").first() is None


def test_route_rejects_a_non_csv_file(app, authenticated_teacher):
    """The roster has to be a CSV."""
    response = post_roster(
        authenticated_teacher, csv_file=upload(ROSTER_CSV.encode(), "roster.xlsx")
    )

    assert "must be a CSV" in response.data.decode()


def test_route_requires_a_domain_name(app, authenticated_teacher):
    """A nameless domain is refused before anything is stored."""
    response = post_roster(authenticated_teacher, domain_name="  ")

    assert "Domain name is required" in response.data.decode()


def test_route_requires_photos(app, authenticated_teacher):
    """Neither a folder nor a zip is an error the teacher can act on."""
    response = post_roster(authenticated_teacher, photo_files=[])

    assert "No photos found" in response.data.decode()


def test_route_cleans_up_when_the_domain_name_is_taken(
    app, authenticated_teacher, populated_db, isolate_uploads
):
    """A rejected domain leaves no uploaded photos behind."""
    response = post_roster(authenticated_teacher, domain_name=populated_db.name)

    assert "already exists" in response.data.decode()
    assert not os.path.exists(isolate_uploads) or os.listdir(isolate_uploads) == []


def test_route_cleans_up_when_a_photo_is_not_an_image(
    app, authenticated_teacher, isolate_uploads
):
    """A junk file in the folder fails the import and stores nothing."""
    response = post_roster(
        authenticated_teacher,
        photo_files=photo_files(["10482", "10483", "10484"])
        + [upload(b"not an image", "10485.jpg")],
    )

    assert "not a recognised image file" in response.data.decode()

    with app.app_context():
        assert Domain.query.filter_by(name="9B Faces").first() is None

    assert not os.path.exists(isolate_uploads) or os.listdir(isolate_uploads) == []


def test_route_is_closed_to_students(app, authenticated_student):
    """Only teachers and admins may import a roster."""
    response = authenticated_student.post(
        "/teacher/domains/import-photos",
        data={"domain_name": "Sneaky"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 403

    with app.app_context():
        assert Domain.query.filter_by(name="Sneaky").first() is None


def test_create_domain_form_offers_the_photo_roster_tab(app, authenticated_teacher):
    """The feature is reachable from the domain creation page."""
    response = authenticated_teacher.get("/teacher/domains/create")
    body = response.data.decode()

    assert "[PHOTO ROSTER]" in body
    assert 'name="photo_files"' in body
    assert "webkitdirectory" in body


def test_create_domain_form_reopens_the_tab_after_a_failure(app, authenticated_teacher):
    """A failed import comes back to the tab it was submitted from."""
    response = authenticated_teacher.get("/teacher/domains/create?tab=photos")

    assert "INITIAL_TAB = 'photos'" in response.data.decode()


# ============================================================================
# QUIZZING AN IMPORTED DOMAIN
# ============================================================================


def test_imported_domain_asks_about_the_photo(app, authenticated_teacher):
    """The imported domain produces name-recognition questions."""
    from quiz_logic import generate_question

    post_roster(authenticated_teacher, include_columns="Surname")

    with app.app_context():
        domain = Domain.query.filter_by(name="9B Faces").first()
        facts = Fact.query.filter_by(domain_id=domain.id).all()

        # Photo as the question, surname as the answer
        question = generate_question(facts[0], "photo", "surname", facts, domain)
        assert question["question"] == "What is the surname of this 9b face?"
        assert question["context_image"] == facts[0].get_fact_data()["photo"]

        # Surname as the question, four photos as the answers
        question = generate_question(facts[0], "surname", "photo", facts, domain)
        assert len(question["options"]) == 4
        assert all(option.startswith("img:") for option in question["options"])
