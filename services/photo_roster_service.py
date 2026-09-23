"""Assemble a domain from a CSV roster plus a folder or zip of photos.

A teacher exports a roster from their school MIS as a CSV whose first column is
an ID, and a photo gallery whose files are named after that same ID:

    ManagementSystemID,Surname,Forename,YearGroup,TutorGroup
    10482,Wright,Alex,Year 9,9B

    photos/10482.jpg

Each row becomes one fact. The ID column is *replaced* by an image field
holding the matching photo - an opaque ID is not worth quizzing - and the
remaining columns become ordinary text fields:

    {"photo": "img:uploads/a3f9c1e8.jpeg", "surname": "Wright",
     "forename": "Alex", "year_group": "Year 9", "tutor_group": "9B"}

The photo field comes first, which makes it the domain's identifying field, so
questions read "What is the surname of this student?" rather than trying to
interpolate an image into the sentence. See services/image_service.py for how
image values are stored and rendered.
"""

import csv
import io
import os
import re
import zipfile

from werkzeug.datastructures import FileStorage

from services.image_service import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_BYTES,
    discard_uploaded_images,
    save_uploaded_image,
)

# Field name used for the photo when the teacher does not choose one.
DEFAULT_PHOTO_FIELD = "photo"

# create_custom_domain() needs four facts to build a multiple-choice question.
MIN_MATCHED_ROWS = 4

# A zip arrives inside a request already capped by MAX_CONTENT_LENGTH, but the
# entries are read into memory, so cap what we are willing to expand.
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_TOTAL_BYTES = 50 * 1024 * 1024

# How many names a report spells out before summarising the rest.
REPORT_SAMPLE_SIZE = 10


def normalise_field_name(header):
    """
    Turn a spreadsheet header into a field name that reads well in a question.

    Questions are built by interpolating the field name ("What is the
    {field} of this student?"), so "YearGroup" has to become "year_group" for
    the quiz to say "year group".

    Args:
        header: Column header as written in the CSV

    Returns:
        str: snake_case field name, or "" if the header has no usable characters
    """
    text = str(header or "")

    # Split CamelCase runs: "DateOfBirth" -> "Date Of Birth" and
    # "ManagementSystemID" -> "Management System ID".
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)

    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    return text.strip("_").lower()


def photo_key(filename):
    """
    Work out which CSV value a photo file belongs to.

    The match is on the basename without its extension, lowercased, so
    "photos/10482.JPG" matches a CSV cell of "10482".

    Args:
        filename: Name of an uploaded file, possibly with a relative path

    Returns:
        str: The key this photo matches, or "" if there is none
    """
    basename = re.split(r"[\\/]", str(filename or ""))[-1]
    stem = os.path.splitext(basename)[0]
    return stem.strip().lower()


def _is_photo_filename(filename):
    """Check a filename looks like an image we accept, by extension."""
    extension = os.path.splitext(str(filename or ""))[1].lower()
    return extension in ALLOWED_EXTENSIONS


def _is_hidden(filename):
    """Check for dot-files, which is also what strips zip __MACOSX entries."""
    basename = re.split(r"[\\/]", str(filename or ""))[-1]
    return basename.startswith(".")


def collect_photo_files(files):
    """
    Index photo files chosen from a folder by the CSV value they match.

    A folder picker submits everything in the directory, so anything that is
    not an image we accept is ignored rather than rejected. Where two files
    share a key ("10482.jpg" and "10482.png") the first one wins.

    Args:
        files: Iterable of werkzeug FileStorage objects

    Returns:
        dict: photo key -> FileStorage
    """
    photos = {}

    for file in files:
        if not file or not file.filename:
            continue
        if _is_hidden(file.filename) or not _is_photo_filename(file.filename):
            continue

        key = photo_key(file.filename)
        if key and key not in photos:
            photos[key] = file

    return photos


def collect_zip_photos(zip_file):
    """
    Index the photos inside an uploaded zip by the CSV value they match.

    Lets a teacher hand over the photo bundle their MIS produced without
    unzipping it first. Entries are read into memory, so both the entry size
    and the expanded total are capped.

    Args:
        zip_file: werkzeug FileStorage holding a .zip

    Returns:
        dict: photo key -> FileStorage

    Raises:
        ValueError: If the file is not a readable zip, or an entry is too large
    """
    photos = {}
    total_bytes = 0

    try:
        archive = zipfile.ZipFile(zip_file)
    except (zipfile.BadZipFile, OSError):
        raise ValueError(f"'{zip_file.filename}' is not a readable zip file")

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ValueError(
                f"The zip holds {len(entries)} entries; the limit is "
                f"{MAX_ZIP_ENTRIES}"
            )

        for entry in entries:
            if entry.is_dir():
                continue
            if _is_hidden(entry.filename) or not _is_photo_filename(entry.filename):
                continue

            key = photo_key(entry.filename)
            if not key or key in photos:
                continue

            # Checked before reading, so an oversized entry is never expanded.
            if entry.file_size > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"'{entry.filename}' in the zip is "
                    f"{entry.file_size // 1024}KB; the limit is "
                    f"{MAX_IMAGE_BYTES // 1024}KB"
                )

            total_bytes += entry.file_size
            if total_bytes > MAX_ZIP_TOTAL_BYTES:
                raise ValueError(
                    f"The zip expands to more than "
                    f"{MAX_ZIP_TOTAL_BYTES // (1024 * 1024)}MB of photos"
                )

            basename = re.split(r"[\\/]", entry.filename)[-1]
            photos[key] = FileStorage(
                stream=io.BytesIO(archive.read(entry)), filename=basename
            )

    return photos


def decode_csv(raw_bytes):
    """
    Decode an uploaded CSV, allowing for the encodings exports come in.

    MIS exports are commonly UTF-8 (often with a BOM) but Windows-1252 turns up
    whenever the file has been through Excel.

    Args:
        raw_bytes: Raw bytes of the uploaded CSV

    Returns:
        str: Decoded CSV text

    Raises:
        ValueError: If neither encoding reads the file
    """
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "The CSV's text could not be read - re-save it as CSV UTF-8 and try again"
    )


def parse_roster_csv(csv_content):
    """
    Read a roster CSV into headers and rows.

    Args:
        csv_content: Decoded CSV text

    Returns:
        tuple: (headers, rows) where rows are dicts keyed by original header

    Raises:
        ValueError: If there is no header row, or fewer than two columns
    """
    reader = csv.DictReader(io.StringIO(csv_content))

    if not reader.fieldnames:
        raise ValueError("The CSV is empty - it needs a header row")

    # Keep the raw field names to read rows by, but present stripped headers.
    headers = [(name or "").strip() for name in reader.fieldnames]

    if len(headers) < 2:
        raise ValueError(
            "The CSV needs at least two columns: the photo filename column "
            "and one detail to quiz"
        )

    rows = [
        {header: row.get(raw) for header, raw in zip(headers, reader.fieldnames)}
        for row in reader
    ]

    return headers, rows


def resolve_included_headers(headers, include_columns=None):
    """
    Decide which detail columns become quizzable fields.

    The first column is always the photo key and is never a field. Teachers
    narrow the rest down when their export carries columns nobody should be
    quizzed on.

    Args:
        headers: All CSV headers, in order
        include_columns: Optional list of column names to keep; names may be
            given as written in the CSV or in normalised form

    Returns:
        list: Headers to turn into fields, in CSV order

    Raises:
        ValueError: If a named column does not exist, or nothing is left
    """
    detail_headers = headers[1:]

    if not include_columns:
        return detail_headers

    by_alias = {}
    for header in detail_headers:
        by_alias[header.lower()] = header
        by_alias[normalise_field_name(header)] = header

    included = []
    for name in include_columns:
        wanted = str(name).strip()
        if not wanted:
            continue

        header = by_alias.get(wanted.lower()) or by_alias.get(
            normalise_field_name(wanted)
        )
        if header is None:
            raise ValueError(
                f"The CSV has no column '{wanted}'. Available columns: "
                f"{', '.join(detail_headers)}"
            )
        if header not in included:
            included.append(header)

    if not included:
        raise ValueError("Choose at least one column to quiz")

    return [header for header in detail_headers if header in included]


def _build_field_names(photo_field, included_headers):
    """
    Map chosen headers to field names, with the photo field first.

    Returns:
        tuple: (field_names, header -> field name)

    Raises:
        ValueError: If a header normalises to nothing or to a duplicate
    """
    fields_by_header = {}
    used = {photo_field: "the photo"}

    for header in included_headers:
        field = normalise_field_name(header)

        if not field:
            raise ValueError(
                f"Column '{header}' has no usable name - rename it in the CSV"
            )
        if field in used:
            raise ValueError(
                f"Column '{header}' and {used[field]} would both become the "
                f"field '{field}' - rename one in the CSV"
            )

        used[field] = f"column '{header}'"
        fields_by_header[header] = field

    return [photo_field] + list(fields_by_header.values()), fields_by_header


def build_photo_facts(
    csv_content, photos, photo_field=DEFAULT_PHOTO_FIELD, include_columns=None
):
    """
    Assemble domain fields and facts from a roster CSV and its photos.

    Rows whose first column matches no photo are skipped and reported rather
    than failing the import - an export routinely covers students whose photo
    is missing. Only matched photos are stored.

    Args:
        csv_content: Decoded CSV text
        photos: photo key -> FileStorage, from collect_photo_files() or
            collect_zip_photos()
        photo_field: Field name to hold the photo
        include_columns: Optional list of detail columns to keep (all by
            default)

    Returns:
        dict:
            field_names: Field names for the domain, photo field first
            facts_data: Fact dicts, one per matched row
            image_values: Stored image values, for rollback on a later failure
            key_column: Header that was used to match photos
            skipped_rows: Keys of rows that had no photo
            blank_rows: Count of rows with an empty first column
            unused_photos: Photo keys no row claimed

    Raises:
        ValueError: If the CSV is unusable, a photo will not store, or fewer
            than MIN_MATCHED_ROWS rows matched a photo
    """
    headers, rows = parse_roster_csv(csv_content)

    photo_field = normalise_field_name(photo_field) or DEFAULT_PHOTO_FIELD
    included_headers = resolve_included_headers(headers, include_columns)
    field_names, fields_by_header = _build_field_names(photo_field, included_headers)

    key_column = headers[0]
    facts_data = []
    stored_by_key = {}
    skipped_rows = []
    blank_rows = 0

    try:
        for row in rows:
            key = (row.get(key_column) or "").strip()
            if not key:
                blank_rows += 1
                continue

            lookup = key.lower()
            if lookup not in photos:
                skipped_rows.append(key)
                continue

            # Two rows may share an ID; store that photo once.
            if lookup not in stored_by_key:
                stored_by_key[lookup] = save_uploaded_image(photos[lookup])

            fact = {photo_field: stored_by_key[lookup]}
            for header, field in fields_by_header.items():
                fact[field] = (row.get(header) or "").strip()
            facts_data.append(fact)

        if len(facts_data) < MIN_MATCHED_ROWS:
            raise ValueError(
                f"Only {len(facts_data)} row(s) matched a photo; at least "
                f"{MIN_MATCHED_ROWS} are needed to build questions. Check that "
                f"the photo files are named after the '{key_column}' column"
            )
    except ValueError:
        discard_uploaded_images(stored_by_key.values())
        raise

    return {
        "field_names": field_names,
        "facts_data": facts_data,
        "image_values": list(stored_by_key.values()),
        "key_column": key_column,
        "skipped_rows": skipped_rows,
        "blank_rows": blank_rows,
        "unused_photos": sorted(set(photos) - set(stored_by_key)),
    }


def _sample(names):
    """Spell out a few names, then say how many more there were."""
    shown = ", ".join(names[:REPORT_SAMPLE_SIZE])
    remaining = len(names) - REPORT_SAMPLE_SIZE
    if remaining > 0:
        return f"{shown} and {remaining} more"
    return shown


def format_import_report(result):
    """
    Describe what an import did and did not take in.

    Args:
        result: Return value of build_photo_facts()

    Returns:
        str: One sentence per thing the teacher may want to fix, or "" if the
            import took in everything
    """
    parts = []

    if result["skipped_rows"]:
        parts.append(
            f"{len(result['skipped_rows'])} row(s) skipped with no matching "
            f"photo: {_sample(result['skipped_rows'])}."
        )

    if result["blank_rows"]:
        parts.append(
            f"{result['blank_rows']} row(s) skipped with a blank "
            f"'{result['key_column']}'."
        )

    if result["unused_photos"]:
        parts.append(
            f"{len(result['unused_photos'])} photo(s) matched no row: "
            f"{_sample(result['unused_photos'])}."
        )

    return " ".join(parts)
