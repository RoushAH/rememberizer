"""Tests for image support in fact fields."""

import io
import json
import os
import pytest

from models import db, Domain, Fact
from quiz_logic import (
    generate_question,
    has_enough_image_distractors,
    prepare_quiz_question_for_fact,
)
from services.image_service import (
    detect_image_type,
    discard_uploaded_images,
    image_reference,
    image_src,
    is_external_reference,
    is_image_value,
    learn_card_alt,
    resolve_image_references,
    save_uploaded_image,
    save_uploaded_images,
)

# Smallest valid files of each type we accept, for upload tests.
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08"
    b"\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20 + b"\xff\xd9"
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 24


def upload(content, filename):
    """Build a FileStorage-like tuple for the test client / direct calls."""
    from werkzeug.datastructures import FileStorage

    return FileStorage(stream=io.BytesIO(content), filename=filename)


@pytest.fixture(autouse=True)
def isolate_upload_config(app, tmp_path):
    """
    Keep uploads out of the real static folder.

    The Flask app is a module-level singleton, so config changes would
    otherwise leak into later tests.
    """
    original_upload_folder = app.config.get("UPLOAD_FOLDER")
    original_static_folder = app.static_folder

    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")

    yield

    app.config["UPLOAD_FOLDER"] = original_upload_folder
    app.static_folder = original_static_folder


@pytest.fixture
def two_field_image_domain(app):
    """
    A domain of name + portrait only.

    With just two fields every question must involve the image, either as the
    context or as the answer options.
    """
    with app.app_context():
        domain = Domain(name="Portrait Domain")
        domain.set_field_names(["name", "portrait"])
        db.session.add(domain)
        db.session.flush()

        for index in range(1, 6):
            fact = Fact(domain_id=domain.id)
            fact.set_fact_data(
                {
                    "name": f"Subject {index}",
                    "portrait": f"img:uploads/portrait{index}.png",
                }
            )
            db.session.add(fact)

        db.session.commit()
        yield domain


@pytest.fixture
def image_domain(app):
    """A domain whose 'portrait' field holds images for every fact."""
    with app.app_context():
        domain = Domain(name="Image Domain")
        domain.set_field_names(["name", "symbol", "portrait"])
        db.session.add(domain)
        db.session.flush()

        for index in range(1, 6):
            fact = Fact(domain_id=domain.id)
            fact.set_fact_data(
                {
                    "name": f"Subject {index}",
                    "symbol": f"Symbol {index}",
                    "portrait": f"img:uploads/portrait{index}.png",
                }
            )
            db.session.add(fact)

        db.session.commit()
        yield domain


# ============================================================================
# MARKER PARSING
# ============================================================================


def test_is_image_value_detects_marker():
    """Only values carrying the marker are images."""
    assert is_image_value("img:uploads/a.png")
    assert is_image_value("img:https://example.org/a.png")
    assert not is_image_value("Lyre")
    assert not is_image_value("")
    assert not is_image_value(None)
    assert not is_image_value(42)


def test_image_reference_strips_marker():
    """The marker is removed to leave a usable reference."""
    assert image_reference("img:uploads/a.png") == "uploads/a.png"
    assert image_reference("Lyre") is None


def test_is_external_reference_requires_https():
    """Only https URLs count as external; http is not accepted."""
    assert is_external_reference("https://example.org/a.png")
    assert not is_external_reference("http://example.org/a.png")
    assert not is_external_reference("uploads/a.png")


def test_image_src_resolves_local_and_external(app):
    """Local references go through static/, external ones are used as-is."""
    with app.test_request_context():
        assert image_src("img:uploads/a.png") == "/static/uploads/a.png"
        assert image_src("img:https://example.org/a.png") == (
            "https://example.org/a.png"
        )
        assert image_src("Lyre") is None


# ============================================================================
# ALT TEXT
# ============================================================================


def test_learn_card_alt_names_the_subject():
    """On the learn card the alt text may describe the image."""
    fact_data = {"name": "Erato", "portrait": "img:uploads/a.png"}
    assert learn_card_alt("portrait", fact_data, "name") == "portrait: Erato"


def test_learn_card_alt_falls_back_without_a_usable_subject():
    """Alt text degrades to the field label when the subject is unusable."""
    # Identifying field is itself an image
    fact_data = {"name": "img:uploads/n.png", "portrait": "img:uploads/a.png"}
    assert learn_card_alt("portrait", fact_data, "name") == "portrait"

    # The image *is* the identifying field
    fact_data = {"name": "img:uploads/n.png"}
    assert learn_card_alt("name", fact_data, "name") == "name"


def test_learn_card_alt_formats_underscored_field_names():
    """Underscores become spaces, matching the rest of the UI."""
    fact_data = {"name": "Erato", "main_portrait": "img:uploads/a.png"}
    assert learn_card_alt("main_portrait", fact_data, "name") == (
        "main portrait: Erato"
    )


# ============================================================================
# UPLOAD VALIDATION
# ============================================================================


def test_detect_image_type_recognises_allowed_formats():
    """Every accepted format is identified from its signature."""
    assert detect_image_type(PNG_BYTES[:12]) == ".png"
    assert detect_image_type(JPEG_BYTES[:12]) == ".jpeg"
    assert detect_image_type(GIF_BYTES[:12]) == ".gif"
    assert detect_image_type(WEBP_BYTES[:12]) == ".webp"
    assert detect_image_type(b"not an image") is None


def test_save_uploaded_image_stores_with_random_name(app, tmp_path):
    """The stored filename does not reveal the original (answer-leaking) name."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        value = save_uploaded_image(upload(PNG_BYTES, "erato.png"))

    assert value.startswith("img:uploads/")
    assert "erato" not in value
    assert value.endswith(".png")

    stored = os.path.basename(image_reference(value))
    assert (tmp_path / stored).read_bytes() == PNG_BYTES


def test_save_uploaded_image_rejects_disallowed_extension(app, tmp_path):
    """An extension outside the allowlist is refused."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        with pytest.raises(ValueError, match="not an allowed image type"):
            save_uploaded_image(upload(PNG_BYTES, "payload.svg"))

    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_image_rejects_non_image_content(app, tmp_path):
    """A file with an image extension but other content is refused."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        with pytest.raises(ValueError, match="not a recognised image file"):
            save_uploaded_image(upload(b"<script>alert(1)</script>", "x.png"))

    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_image_rejects_extension_content_mismatch(app, tmp_path):
    """A GIF named .png is refused rather than silently stored."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        with pytest.raises(ValueError, match="contains .gif data"):
            save_uploaded_image(upload(GIF_BYTES, "sneaky.png"))


def test_save_uploaded_image_accepts_jpg_as_jpeg(app, tmp_path):
    """.jpg and .jpeg are the same format and both work."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        value = save_uploaded_image(upload(JPEG_BYTES, "photo.jpg"))

    assert value.endswith(".jpeg")


def test_save_uploaded_image_rejects_oversized_file(app, tmp_path, monkeypatch):
    """A file over the per-image cap is refused."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    monkeypatch.setattr("services.image_service.MAX_IMAGE_BYTES", 10)

    with app.app_context():
        with pytest.raises(ValueError, match="the limit is"):
            save_uploaded_image(upload(PNG_BYTES, "big.png"))

    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_image_strips_path_from_filename(app, tmp_path):
    """A traversal attempt in the filename cannot escape the upload folder."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        value = save_uploaded_image(upload(PNG_BYTES, "../../evil.png"))

    assert ".." not in value
    assert len(list(tmp_path.iterdir())) == 1


def test_save_uploaded_images_cleans_up_after_a_rejection(app, tmp_path):
    """A bad file in the batch leaves no half-saved uploads behind."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        with pytest.raises(ValueError):
            save_uploaded_images(
                [
                    upload(PNG_BYTES, "good.png"),
                    upload(b"junk", "bad.png"),
                ]
            )

    assert list(tmp_path.iterdir()) == []


def test_save_uploaded_images_skips_empty_inputs(app, tmp_path):
    """Unfilled file inputs are ignored rather than erroring."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        saved = save_uploaded_images([upload(b"", ""), None])

    assert saved == {}


def test_discard_uploaded_images_removes_stored_files(app, tmp_path):
    """Discarding deletes the file from disk."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    app.static_folder = str(tmp_path)

    with app.app_context():
        value = save_uploaded_image(upload(PNG_BYTES, "a.png"))
        assert os.path.exists(os.path.join(tmp_path, image_reference(value)))

        discard_uploaded_images([value])
        assert not os.path.exists(os.path.join(tmp_path, image_reference(value)))


def test_discard_uploaded_images_ignores_paths_outside_uploads(app, tmp_path):
    """Discarding will not delete anything outside the upload folder."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    app.static_folder = str(tmp_path)
    victim = tmp_path / "style.css"
    victim.write_text("keep me")

    with app.app_context():
        discard_uploaded_images(
            ["img:style.css", "img:uploads/../style.css", "img:https://x/y.png"]
        )

    assert victim.read_text() == "keep me"


# ============================================================================
# REFERENCE RESOLUTION
# ============================================================================


def test_resolve_image_references_rewrites_uploaded_filenames():
    """A friendly reference becomes the stored path."""
    facts = [{"name": "Erato", "portrait": "img:erato.png"}]
    uploaded = {"erato.png": "img:uploads/abc123.png"}

    resolved = resolve_image_references(facts, uploaded)

    assert resolved == [{"name": "Erato", "portrait": "img:uploads/abc123.png"}]


def test_resolve_image_references_matches_case_insensitively():
    """Teachers' capitalisation of a filename does not have to match."""
    facts = [{"portrait": "img:Erato.PNG"}]
    uploaded = {"erato.png": "img:uploads/abc123.png"}

    resolved = resolve_image_references(facts, uploaded)

    assert resolved[0]["portrait"] == "img:uploads/abc123.png"


def test_resolve_image_references_keeps_external_urls():
    """An https reference is passed through untouched."""
    facts = [{"portrait": "img:https://example.org/a.png"}]

    resolved = resolve_image_references(facts, {})

    assert resolved[0]["portrait"] == "img:https://example.org/a.png"


def test_resolve_image_references_leaves_text_values_alone():
    """Non-image values are untouched."""
    facts = [{"name": "Erato", "symbol": "Lyre"}]

    assert resolve_image_references(facts, {}) == facts


def test_resolve_image_references_rejects_unknown_filename():
    """A reference with no matching upload is an error, not a broken image."""
    facts = [{"portrait": "img:missing.png"}]

    with pytest.raises(ValueError, match="No uploaded image named 'missing.png'"):
        resolve_image_references(facts, {})


def test_resolve_image_references_rejects_traversal_attempt():
    """A hand-written path cannot reach files outside the uploads."""
    facts = [{"portrait": "img:../../instance/database.db"}]

    with pytest.raises(ValueError, match="No uploaded image named"):
        resolve_image_references(facts, {})


def test_resolve_image_references_rejects_non_https_url():
    """A plain http URL is called out specifically."""
    facts = [{"portrait": "img:http://example.org/a.png"}]

    with pytest.raises(ValueError, match="must use https://"):
        resolve_image_references(facts, {})


# ============================================================================
# QUESTION GENERATION
# ============================================================================


def test_question_points_at_image_context_instead_of_interpolating(app, image_domain):
    """An image context becomes 'this <field>' plus a returned image."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=image_domain.id).all()

        question_data = generate_question(
            facts[0], "portrait", "symbol", facts, image_domain
        )

    assert question_data["question"] == (
        "What is the symbol of the image domain with this portrait?"
    )
    assert "img:" not in question_data["question"]
    assert question_data["context_image"] == "img:uploads/portrait1.png"


def test_question_with_image_context_and_name_answer(app, image_domain):
    """Asking for the name off an image reads as 'Which X has this Y?'."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=image_domain.id).all()

        question_data = generate_question(
            facts[0], "portrait", "name", facts, image_domain
        )

    assert question_data["question"] == "Which image domain has this portrait?"
    assert question_data["context_image"] == "img:uploads/portrait1.png"


def test_question_with_image_answer_offers_image_options(app, image_domain):
    """An image field as the answer yields four image options."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=image_domain.id).all()

        question_data = generate_question(
            facts[0], "name", "portrait", facts, image_domain
        )

    assert question_data["question"] == "What is the portrait of Subject 1?"
    assert question_data["context_image"] is None
    assert len(question_data["options"]) == 4
    assert all(is_image_value(option) for option in question_data["options"])
    assert question_data["correct_answer"] == "img:uploads/portrait1.png"


def test_text_questions_keep_their_wording_and_report_no_image(app, populated_db):
    """Domains without images are unaffected by image support."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).all()

        question_data = generate_question(
            facts[0], "name", "category", facts, populated_db
        )

    assert question_data["question"] == "What is the category of Fact 1?"
    assert question_data["context_image"] is None


def test_prepare_quiz_question_for_fact_reports_context_image(app, image_domain):
    """The prepared question always carries a context_image key."""
    with app.app_context():
        fact = Fact.query.filter_by(domain_id=image_domain.id).first()

        question_data = prepare_quiz_question_for_fact(fact, image_domain.id)

    assert "context_image" in question_data
    context_field = question_data["context_field"]
    if context_field == "portrait":
        assert question_data["context_image"] == "img:uploads/portrait1.png"
    else:
        assert question_data["context_image"] is None


# ============================================================================
# OPTION GRID GUARD
# ============================================================================


def test_has_enough_image_distractors_passes_text_fields(app, populated_db):
    """Text answers never need the image check."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=populated_db.id).all()

        assert has_enough_image_distractors(facts[0], "category", facts)


def test_has_enough_image_distractors_accepts_distinct_images(app, image_domain):
    """Five distinct images give any one fact three distractors."""
    with app.app_context():
        facts = Fact.query.filter_by(domain_id=image_domain.id).all()

        assert has_enough_image_distractors(facts[0], "portrait", facts)


def test_has_enough_image_distractors_rejects_duplicate_images(app):
    """Facts sharing one image cannot fill an all-image grid."""
    with app.app_context():
        domain = Domain(name="Duplicate Images")
        domain.set_field_names(["name", "portrait"])
        db.session.add(domain)
        db.session.flush()

        for index in range(1, 5):
            fact = Fact(domain_id=domain.id)
            fact.set_fact_data(
                {"name": f"Subject {index}", "portrait": "img:uploads/same.png"}
            )
            db.session.add(fact)
        db.session.commit()

        facts = Fact.query.filter_by(domain_id=domain.id).all()

        assert not has_enough_image_distractors(facts[0], "portrait", facts)


# ============================================================================
# TEMPLATE RENDERING
# ============================================================================


def test_show_fact_renders_an_img_tag(app, authenticated_student, image_domain):
    """The learn card renders images instead of printing the marker."""
    with app.app_context():
        fact = Fact.query.filter_by(domain_id=image_domain.id).first()
        fact_id = fact.id

    response = authenticated_student.get(f"/show_fact/{fact_id}")
    body = response.data.decode()

    assert response.status_code == 200
    assert '<img class="fact-image"' in body
    assert 'src="/static/uploads/portrait1.png"' in body
    assert 'alt="portrait: Subject 1"' in body
    assert "img:uploads/portrait1.png" not in body


def test_quiz_renders_image_options_with_generic_alt_text(
    app, client, student_user, teacher_user, two_field_image_domain
):
    """Image options render as pictures whose alt text hides the answer."""
    from services.domain_service import assign_domain_to_user
    from services.fact_service import mark_fact_learned

    domain = two_field_image_domain

    with app.app_context():
        assign_domain_to_user(student_user.id, domain.id, teacher_user.id)

        facts = Fact.query.filter_by(domain_id=domain.id).all()
        for fact in facts:
            mark_fact_learned(fact.id, student_user.id)

        fact_id = facts[0].id

    client.post(
        "/login",
        data={"email": "student@test.com", "password": "studentpass123"},
        follow_redirects=True,
    )

    with client.session_transaction() as session:
        session["domain_id"] = domain.id
        session["question_count"] = 0
        session["pending_quiz_fact_id"] = fact_id

    response = client.get("/quiz")
    body = response.data.decode()

    assert response.status_code == 200
    # Whichever way round the pair came out, no raw marker reaches the page
    assert "img:uploads/" not in body

    if '<img class="option-image"' in body:
        # The portrait is the answer: alt text must not name the subject
        assert 'alt="Option 1"' in body
        assert "Subject 1" not in body.split('class="options"')[1]
    else:
        # The portrait is the context
        assert '<img class="question-image"' in body
        assert 'alt="Image referred to by the question"' in body


# ============================================================================
# DOMAIN CREATION WITH IMAGES
# ============================================================================


def test_create_domain_form_stores_uploaded_image_paths(
    app, authenticated_teacher, tmp_path
):
    """Form entry resolves img: references against the uploaded files."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    facts = [{"name": f"Subject {i}", "portrait": f"img:p{i}.png"} for i in range(1, 5)]

    response = authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "form",
            "domain_name": "Uploaded Images",
            "field_names": "name, portrait",
            "facts_json": json.dumps(facts),
            "image_files": [upload(PNG_BYTES, f"p{i}.png") for i in range(1, 5)],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        domain = Domain.query.filter_by(name="Uploaded Images").first()
        assert domain is not None

        portraits = [
            fact.get_fact_data()["portrait"]
            for fact in Fact.query.filter_by(domain_id=domain.id).all()
        ]

    # Each reference became a distinct stored path, not the original name
    assert len(set(portraits)) == 4
    for portrait in portraits:
        assert portrait.startswith("img:uploads/")
        assert ".png" in portrait
    assert not any("p1.png" in portrait for portrait in portraits)
    assert len(list(tmp_path.iterdir())) == 4


def test_create_domain_form_accepts_external_urls_without_upload(
    app, authenticated_teacher
):
    """An https reference needs no uploaded file."""
    facts = [
        {"name": f"Subject {i}", "portrait": f"img:https://example.org/{i}.png"}
        for i in range(1, 5)
    ]

    authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "form",
            "domain_name": "External Images",
            "field_names": "name, portrait",
            "facts_json": json.dumps(facts),
        },
        follow_redirects=True,
    )

    with app.app_context():
        domain = Domain.query.filter_by(name="External Images").first()
        assert domain is not None

        fact = Fact.query.filter_by(domain_id=domain.id).first()
        assert fact.get_fact_data()["portrait"].startswith("img:https://")


def test_create_domain_rejects_unmatched_image_reference(
    app, authenticated_teacher, tmp_path
):
    """A missing upload fails the whole creation and cleans up."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    facts = [
        {"name": f"Subject {i}", "portrait": "img:nowhere.png"} for i in range(1, 5)
    ]

    response = authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "form",
            "domain_name": "Broken Images",
            "field_names": "name, portrait",
            "facts_json": json.dumps(facts),
            "image_files": [upload(PNG_BYTES, "unrelated.png")],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "No uploaded image named" in response.data.decode()

    with app.app_context():
        assert Domain.query.filter_by(name="Broken Images").first() is None

    # The unrelated upload was not left behind
    assert list(tmp_path.iterdir()) == []


def test_create_domain_rejects_bad_image_upload(app, authenticated_teacher, tmp_path):
    """A file that is not an image blocks creation."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    facts = [{"name": f"Subject {i}", "portrait": "img:fake.png"} for i in range(1, 5)]

    response = authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "form",
            "domain_name": "Fake Images",
            "field_names": "name, portrait",
            "facts_json": json.dumps(facts),
            "image_files": [upload(b"not an image at all", "fake.png")],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "not a recognised image file" in response.data.decode()

    with app.app_context():
        assert Domain.query.filter_by(name="Fake Images").first() is None

    assert list(tmp_path.iterdir()) == []


def test_create_domain_csv_resolves_image_references(
    app, authenticated_teacher, tmp_path
):
    """CSV cells carrying img: references are resolved the same way."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    csv_content = (
        "name,portrait\n"
        "Subject 1,img:c1.png\n"
        "Subject 2,img:c2.gif\n"
        "Subject 3,img:https://example.org/c3.png\n"
        "Subject 4,img:c4.jpg\n"
    )

    response = authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "csv",
            "domain_name": "CSV Images",
            "csv_file": upload(csv_content.encode(), "facts.csv"),
            "image_files": [
                upload(PNG_BYTES, "c1.png"),
                upload(GIF_BYTES, "c2.gif"),
                upload(JPEG_BYTES, "c4.jpg"),
            ],
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        domain = Domain.query.filter_by(name="CSV Images").first()
        assert domain is not None

        by_name = {
            fact.get_fact_data()["name"]: fact.get_fact_data()["portrait"]
            for fact in Fact.query.filter_by(domain_id=domain.id).all()
        }

    assert by_name["Subject 1"].endswith(".png")
    assert by_name["Subject 2"].endswith(".gif")
    assert by_name["Subject 4"].endswith(".jpeg")
    assert by_name["Subject 3"] == "img:https://example.org/c3.png"

    for name in ("Subject 1", "Subject 2", "Subject 4"):
        assert by_name[name].startswith("img:uploads/")


def test_create_domain_without_images_still_works(app, authenticated_teacher):
    """Adding image support did not change plain domain creation."""
    facts = [{"name": f"Subject {i}", "value": f"Value {i}"} for i in range(1, 5)]

    authenticated_teacher.post(
        "/teacher/domains/create",
        data={
            "upload_method": "form",
            "domain_name": "Plain Domain",
            "field_names": "name, value",
            "facts_json": json.dumps(facts),
        },
        follow_redirects=True,
    )

    with app.app_context():
        domain = Domain.query.filter_by(name="Plain Domain").first()
        assert domain is not None
        assert Fact.query.filter_by(domain_id=domain.id).count() == 4
