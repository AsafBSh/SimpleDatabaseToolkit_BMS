"""Distribution capabilities; the public source export disables private modules."""

# Full local development and release binaries include the BML implementation.
# tools/export_public_source.py generates False in the separate public checkout.
BML_EDITOR_ENABLED = False


def page_enabled(page_id: str) -> bool:
    return page_id != "bml" or BML_EDITOR_ENABLED
