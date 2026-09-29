# Montage Wallpaper

A Python script that generates desktop wallpaper montages from a folder of images. It uses a pseudo-Poisson dart-throwing algorithm to place randomly sized, tilted, bordered, and shadowed photos onto a canvas, creating a scattered photo collage effect.

## Requirements

- Python 3
- [Pillow](https://pillow.readthedocs.io/) (PIL)

## Setup

This is a [uv](https://docs.astral.sh/uv/) project. Install dependencies with:

```bash
uv sync
```

## Usage

```bash
uv run Montage.py [options] src_folder output_image
uv run Montage.py [options] --screen width height output_image [--screen ...] src_folder
```

### Arguments

| Argument       | Description                                      |
|----------------|--------------------------------------------------|
| `src_folder`   | Path to a folder of images (`.jpg`, `.jpeg`, `.gif`, `.bmp`, `.png`) |
| `output_image` | Path for the output montage image (omit when using `--screen`) |

### Options

| Option                              | Description                                              | Default |
|-------------------------------------|----------------------------------------------------------|---------|
| `--screen width height output`      | Size and output path of one screen (repeatable). Photos are not repeated across screens until all have been used | none |
| `-s, --size width height`           | Size of the output image in pixels                       | required without `--screen` |
| `-r, --region x_min y_min x_max y_max` | Rectangular sub-region for placing images (repeatable) | full image |
| `--big diameter`                    | Maximum dimension of the biggest pictures                | 256     |
| `--small diameter`                  | Maximum dimension of the smallest pictures               | 128     |
| `--steps N`                         | Number of size steps between big and small               | 2       |
| `--maxtrys N`                       | Maximum placement attempts per size step                 | 10000   |
| `--scale factor`                    | Scale factor for the output image                        | 1       |
| `--aafactor factor`                 | Anti-aliasing supersampling factor                       | 2       |
| `--overlap fraction`               | Fraction that images may overlap                         | 0.5     |
| `--tilt angle`                      | Maximum random tilt angle in degrees                     | 15      |
| `--border width`                    | Width of white border around each picture (pixels)       | 5       |
| `--shadow width`                    | Width of drop shadow under each picture (pixels)         | 5       |
| `--seed value`                      | Random seed for reproducible layouts                     | None    |
| `-v, --verbose`                     | Produce verbose output                                   | off     |
| `--placement-log path`              | CSV file listing every placed photo                      | `montage-placements-YYYYMMDD-HHMMSS.csv` next to the first output |
| `--fit suggest\|auto`               | Pick `--big` and `--small` so the screens hold about as many photos as the folder has. `suggest` prints the values and exits; `auto` uses them | off |
| `--keep log output`                 | Treat `output`, as recorded in placement log `log`, as a finished screen whose photos the new screens avoid (repeatable) | none |

### Example

```bash
uv run Montage.py --size 1920 1080 --big 300 --small 100 --tilt 20 ~/Photos montage.jpg
```

This generates a 1920x1080 montage from images in `~/Photos` and saves it to `montage.jpg`.

### Example: multiple screens

To make a wallpaper for each screen in a multi-monitor setup, pass `--screen` once per screen. All screens draw from the same shuffled set of photos, so no photo appears twice, on one screen or across screens, until every photo has been used:

```bash
uv run Montage.py \
  --screen 3440 1440 wallpaper-left.jpg \
  --screen 1728 1117 wallpaper-center.jpg \
  --screen 1920 1080 wallpaper-right.jpg \
  ~/Photos
```

If the screens need more photos than the folder has, some photos are reused on a later screen, but never twice on the same screen. If a screen still needs more, the extra spots stay empty. Raise `--big` and `--small` to use fewer, larger photos, or let `--fit` choose them (see below). Run with `-v` to see how many spots each screen has (`disks placed`) and whether photos were reused.

`--screen` cannot be combined with `output_image`, `--size`, or `--region`.

### Example: fit the photo size to the folder

`--fit` picks `--big` and `--small` so that all screens together have room for about as many photos as the folder has, without going over. Every photo then appears once, with none repeated. It keeps the ratio between `--small` and `--big`, starting from their current values.

Preview the values without making any images:

```bash
uv run Montage.py --fit suggest \
  --screen 3440 1440 wallpaper-left.jpg \
  --screen 1728 1117 wallpaper-center.jpg \
  --screen 1920 1080 wallpaper-right.jpg \
  ~/Photos
# --big 277 --small 139 fits 316 pictures for 323 images (173 on wallpaper-left.jpg, ...)
```

Use `--fit auto` instead to choose the values and make the wallpapers in one step. Layouts are random, so the suggested values vary a little from run to run. A later run with the suggested values can place a slightly different number of photos. `--fit auto` has no such drift: it renders the exact layout it measured.

### Example: keep one screen, redo the others

When one screen stays the same everywhere (say, a laptop's built-in display) and the external displays change from place to place, make the fixed screen once, then use `--keep` to build the other screens around it. `--keep` takes a placement log and the name of an output in that log. That screen is not redrawn, and its photos are not used on the new screens until every other photo has been used. With `--fit`, only the photos that are not on kept screens are counted.

```bash
# at work: laptop plus two 2560x1440 displays
uv run Montage.py --fit auto \
  --screen 1728 1117 wallpaper-laptop.jpg \
  --screen 2560 1440 wallpaper-work-1.jpg \
  --screen 2560 1440 wallpaper-work-2.jpg \
  --placement-log placements-work.csv ~/Photos

# at home: keep the laptop screen, make new screens for the home displays
uv run Montage.py --fit auto \
  --keep placements-work.csv wallpaper-laptop.jpg \
  --screen 3440 1440 wallpaper-home-left.jpg \
  --screen 1920 1080 wallpaper-home-right.jpg \
  --placement-log placements-home.csv ~/Photos
```

The new log also includes the kept screen's rows, so any log can be the source for a later `--keep`. A kept output cannot also be one of this run's outputs. Photos are matched by path, so run from the same directory and pass the same folder as the run that made the log. Photos listed in the log that are no longer in the folder are ignored.

## Notes

- Progress goes to stdout and warnings and errors to stderr. Redirect them if you want a log file, e.g. `uv run Montage.py ... > montage.log 2>&1`.
- Every run writes a placement log (see `--placement-log`), a CSV file with one row per placed photo: `output`, `image`, `x`, `y`, `width`, `height`, `angle`. `x` and `y` are the top-left corner, and `width` and `height` are the size, in pixels of the saved image, including the photo's border, shadow and tilt. `angle` is the tilt in degrees. The default file name includes the date and time, so each run keeps its own log.
- The script supports EXIF orientation correction for rotated camera photos.
- The `output_image` path supports environment variable substitution (e.g., `%(HOME)s/wallpaper.png`).

## Acknowledgements

With huge thanks to [Dr. Gary Bishop](https://www.cs.unc.edu/~gb/) for all his mentorship, but most specifically for [the OG](https://gist.github.com/gbishop/524321).