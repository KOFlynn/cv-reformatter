"""image_leak: hashes in, findings out. A hash is any content digest string."""

from cvr.eval import Finding, image_leak

LOGO = "sha256:0f0f0f0f0f0f0f0f"
PHOTO = "sha256:abababababababab"


def test_no_images_anywhere_is_clean():
    assert image_leak([], []) == []


def test_an_output_image_that_is_a_template_image_is_not_a_leak():
    assert image_leak([LOGO], [LOGO]) == []


def test_an_output_image_not_in_the_template_is_a_finding_counted_in_the_output():
    assert image_leak([LOGO, PHOTO], [LOGO]) == [
        Finding(what=PHOTO, count=1, where="output")
    ]


def test_the_same_foreign_image_twice_is_one_finding_of_two():
    assert image_leak([PHOTO, PHOTO], []) == [
        Finding(what=PHOTO, count=2, where="output")
    ]


def test_a_template_image_the_output_repeats_is_not_a_leak():
    # Membership, not multiplicity: a logo in every section header is still
    # the template's own image.
    assert image_leak([LOGO, LOGO], [LOGO]) == []


def test_findings_are_sorted_by_hash():
    assert image_leak(["sha256:ff", "sha256:aa"], []) == [
        Finding(what="sha256:aa", count=1, where="output"),
        Finding(what="sha256:ff", count=1, where="output"),
    ]
