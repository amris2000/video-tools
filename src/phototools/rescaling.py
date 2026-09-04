from pathlib import Path
from PIL import ImageOps, Image

ROOT = Path(r"C:\Users\Frederik\Bryllup\processed_pictures\jpg_export")   # <-- change this
POSTFIX = "_half_size"
SCALING = 2
DRY_RUN = False

DEST_ROOT = ROOT.parent / f"{ROOT.name}{POSTFIX}"

print("\n=== IMAGE RESIZE SCRIPT ===")
print(f"Source root:      {ROOT}")
print(f"Destination root: {DEST_ROOT}")
print(f"Postfix used:     {POSTFIX}")
print(f"Dry run:          {DRY_RUN}")
print("===========================\n")

file_count = 0
folders_created = set()

for src_path in ROOT.rglob("*"):
    if src_path.is_file() and src_path.suffix.lower() in [".jpg", ".jpeg"]:

        file_count += 1

        relative = src_path.relative_to(ROOT)

        new_parts = [
            p + POSTFIX if i < len(relative.parts) - 1 else p
            for i, p in enumerate(relative.parts)
        ]

        dest_path = DEST_ROOT.joinpath(*new_parts)

        # Folder reporting
        if dest_path.parent not in folders_created:
            folders_created.add(dest_path.parent)
            print(f"[DIR ] Would create: {dest_path.parent}")

            if not DRY_RUN:
                dest_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[FILE] {src_path}")
        print(f"       → {dest_path}")

        if not DRY_RUN:
            with Image.open(src_path) as img:
                img = ImageOps.exif_transpose(img)   # <-- FIX ORIENTATION

                w, h = img.size
                resized = img.resize((w // SCALING, h // SCALING), Image.LANCZOS)
                resized.save(dest_path, quality=90, optimize=True)

        print()

print(f"\nSummary:")
print(f"Images found: {file_count}")
print(f"Folders:      {len(folders_created)}")

if DRY_RUN:
    print("\n*** DRY RUN — no files were created or modified ***\n")
else:
    print("\nProcessing complete.\n")
