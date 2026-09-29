#!/usr/bin/env python3
'''Yet another Montage experiment for desktop wallpaper

This version works with a variant on the "Pseudo-Poisson" dart throwing algorithms
that were popular in stochastic ray-tracing years ago. It throws darts at a rectangular
region ensuring that no darts are closer together than a minimum distance. It allows the
minimum distance to scale down so you can have some big pictues and some smaller pictures.

The help text was intended to be self explanatory...

'''

import sys

from PIL import Image

import csv
import datetime
import math
import os
import random
from argparse import ArgumentParser

class Disk(object):
  '''A circular region'''
  def __init__(self, center, radius):
    '''Create a disk from a complex center and float radius.'''
    self.center = center
    self.radius = radius

  def range(self, other):
    '''Compute the distance between two disks.'''
    return abs(self.center - other.center)

  def overlaps(self, other):
    '''True if one disk overlaps the other'''
    return self.range(other) < self.radius + other.radius

  def __str__(self):
    return 'Disk((%.1f, %.1f), %.1f)' % (self.center.real, self.center.imag, self.radius)
  
class Field(object):
  '''A rectangular field of non-overlapping disks.'''
  def __init__(self, width, height):
    '''Initialize a field with integer width and height'''
    self.width = width
    self.height = height
    self.disks = []

  def insert(self, new_disk):
    '''Insert a disk if it does not overlap others, return True for insertion.'''
    for disk in self.disks:
      if new_disk.overlaps(disk):
        return False
    self.disks.append(new_disk)
    return True

  def insert_random(self, radius):
    '''Try inserting a disk at a random location within the field'''
    x = random.uniform(radius, self.width-radius)
    y = random.uniform(radius, self.height-radius)
    return self.insert(Disk(complex(x,y), radius))

  def len(self):
    return len(self.disks)

  def __getitem__(self, ndx):
    return self.disks[ndx]

def add_border(im, picture_border):
  isize = im.size
  osize = (isize[0]+2*picture_border, isize[1]+2*picture_border)
  om = Image.new('RGB', osize, (255,255,255))
  om.paste(im, (picture_border,picture_border))
  return om

def add_shadow(im, shadow_offset):
  isize = im.size
  osize = (isize[0]+abs(shadow_offset), isize[1]+abs(shadow_offset))
  om = Image.new('RGBA', osize, (255,255,255,0))
  shadow = Image.new('RGBA', isize, (0,0,0,120))
  om.paste(shadow, (max(0,shadow_offset), max(0,shadow_offset)))
  om.paste(im, (-min(0,shadow_offset),-min(0,shadow_offset)))
  return om

def rotate(im, angle):
  isize = im.size
  big = int(math.sqrt(isize[0]**2 + isize[1]**2))
  osize = (big,big)  
  om = Image.new('RGBA', osize, (0,0,0,0))
  om.paste(im, ((big-isize[0])//2, (big-isize[1])//2))
  om = om.rotate(angle, Image.BICUBIC)
  return om.crop(om.getbbox())

parser = ArgumentParser(description='Generate a montage wallpaper from a folder of images.')
parser.add_argument('image_dir', help='source folder of images')
parser.add_argument('result_name', nargs='?', help='output image path (omit when using --screen)')
parser.add_argument('--screen', action='append', nargs=3, dest='screens',
                    metavar=('width', 'height', 'output'),
                    help='size and output path of one screen, you can have several of these. No picture is repeated across screens until every picture has been used.')
parser.add_argument('-r', '--region', action='append', type=int, nargs=4, dest='regions',
                    metavar=('x_min', 'y_min', 'x_max', 'y_max'), help='limits of a rectangular image region, you can have several of these. Useful for avoiding the seam between multiple displays.')
parser.add_argument('-s', '--size', type=int, nargs=2, dest='size',
                    help='size of the output image', metavar=('width', 'height'))
parser.add_argument('--big', type=float, dest='big', metavar='diameter',
                    help='maximum dimension of biggest pictures', default=256)
parser.add_argument('--small', type=float, dest='small', metavar='diameter',
                    help='maximum dimension of smallest pictures', default=128)
parser.add_argument('--steps', type=int, dest='steps',
                    help='number of steps between BIG and SMALL', default=2)
parser.add_argument('--maxtrys', type=int, dest='maxtrys',
                    help='maximum number of attempts to place an image', default=10000)
parser.add_argument('--scale', type=float, dest='scale',
                    help='scale factor for output image', default=1)
parser.add_argument('--aafactor', type=float, dest='aafactor',
                    help='scale factor for antialiasing output image', default=2)
parser.add_argument('--overlap', type=float, dest='overlap',
                    help='fraction that images may overlap', default=0.5)
parser.add_argument('--tilt', type=float, dest='tilt',
                    help='maximum angle of tilt', metavar='ANGLE', default=15)
parser.add_argument('--border', type=int, dest='border',
                    help='width of white border on pictures', default=5)
parser.add_argument('--shadow', type=int, dest='shadow',
                    help='width of shadow under pictures', default=5)
parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                    help='produce verbose output', default=False)
parser.add_argument('--seed', dest='seed', default=None)
parser.add_argument('--placement-log', dest='placement_log', metavar='path', default=None,
                    help='CSV file listing every placed image, its output file and coordinates (default: montage-placements-TIMESTAMP.csv next to the first output)')
parser.add_argument('--fit', choices=['suggest', 'auto'], dest='fit', default=None,
                    help='choose BIG and SMALL so all screens together hold about as many pictures as the source folder has. suggest prints the values and exits, auto uses them.')
parser.add_argument('--keep', action='append', nargs=2, dest='keeps', default=[],
                    metavar=('log', 'output'),
                    help='treat OUTPUT, as recorded in placement log LOG, as a finished screen: it is not redrawn, its pictures are not used on the other screens until every picture has been used, and --fit only counts the pictures left over. You can have several of these.')

options = parser.parse_args()
image_dir = options.image_dir

if options.screens:
  if options.result_name or options.size or options.regions:
    parser.error('--screen cannot be combined with result_name, --size or --region')
elif not options.result_name:
  parser.error('result_name is required unless --screen is given')
elif not options.size:
  parser.error('--size is required unless --screen is given')

def same_path(a, b):
  return os.path.normpath(a) == os.path.normpath(b)

# rows from placement logs for screens that are already finished
kept_rows = []
for log_path, kept_output in options.keeps:
  try:
    with open(log_path, newline='') as f:
      rows = list(csv.DictReader(f))
  except OSError as e:
    parser.error('--keep cannot read %s: %s' % (log_path, e))
  matches = [ row for row in rows if same_path(row['output'], kept_output) ]
  if not matches:
    outputs = sorted(set(row['output'] for row in rows))
    parser.error('--keep: %s has no placements for %s (it has: %s)'
                 % (log_path, kept_output, ', '.join(outputs) or 'nothing'))
  kept_rows.extend(matches)
  if not os.path.exists(kept_output):
    print('warning: kept screen %s does not exist' % kept_output, file=sys.stderr)

new_outputs = [ screen[2] for screen in options.screens ] if options.screens else [ options.result_name ]
for log_path, kept_output in options.keeps:
  if any(same_path(kept_output, name) for name in new_outputs):
    parser.error('--keep %s would be overwritten by this run' % kept_output)

random.seed(options.seed)

# each job is (size, regions, result_name) for one output image
if options.screens:
  jobs = []
  for width, height, name in options.screens:
    width, height = int(width), int(height)
    jobs.append(((width, height), [ (0,0,width,height) ], name))
else:
  if options.regions is None:
    options.regions = [ (0,0,options.size[0],options.size[1]) ]
  jobs = [ (options.size, options.regions, options.result_name) ]

class ImagePool(object):
  '''Hands out images in random order without repeats until every image has been used.'''
  def __init__(self, names, already_used=()):
    '''already_used images are held back until the rest have been used.'''
    self.names = names
    self.unused = [ name for name in names if name not in already_used ]
    random.shuffle(self.unused)

  def take(self, exclude):
    '''Return an image name not in exclude, or None if there are none left.'''
    if not self.unused:
      # every image has been used once, start reusing the ones not on this output
      self.unused = [ name for name in self.names if name not in exclude ]
      random.shuffle(self.unused)
      if self.unused:
        print('ran out of images, reusing some', file=sys.stderr)
    if not self.unused:
      return None
    return self.unused.pop()

def place_disks(regions, big, small):
  '''Allocate space for pictures in each region.'''
  fields = [ Field(region[2]-region[0], region[3]-region[1])
             for region in regions ]
  if options.verbose:
    print('Placing disks')
  for field in fields:
    scale = (float(small) / big) ** (1.0/options.steps)
    radius = big / (2 * (1 + options.overlap))
    for step in range(options.steps+1):
      inserted = 0
      for i in range(options.maxtrys):
        if field.insert_random(radius):
          inserted += 1
      radius *= scale
    if options.verbose:
      print(field.len(), 'disks placed')
  return fields

def count_disks(layouts):
  return sum(field.len() for fields in layouts for field in fields)

def fit_layouts(image_count):
  '''Find BIG and SMALL so the total number of disks is close to, but not over, image_count.

  Keeps the ratio of SMALL to BIG. The disk count goes roughly as 1/BIG**2, so
  each attempt rescales BIG by the square root of how far off the count was.
  Returns the best layouts found along with their BIG and SMALL.'''
  ratio = float(options.small) / options.big
  big = options.big
  best = None
  for attempt in range(8):
    layouts = [ place_disks(regions, big, big*ratio) for size, regions, name in jobs ]
    total = count_disks(layouts)
    if options.verbose:
      print('fit attempt %d: big=%.0f small=%.0f gives %d disks for %d images'
            % (attempt+1, big, big*ratio, total, image_count))
    if total <= image_count and (best is None or total > count_disks(best[0])):
      best = (layouts, big, big*ratio)
    if best and count_disks(best[0]) >= 0.95 * image_count:
      break
    # aim slightly low since random placement makes the count noisy
    big *= math.sqrt(total / (0.97 * image_count))
  if best is None:
    best = (layouts, big, big*ratio)
  return best

def render(size, regions, fields, pool, result_name, log):
  '''Build one montage image, taking pictures from the shared pool and logging each placement.'''
  scaleup = options.scale * options.aafactor
  scaledown = options.aafactor

  out_size = (int(size[0]*scaleup), int(size[1]*scaleup))
  out = Image.new('RGB', out_size, (0,0,0))
  used = set()

  for i,field in enumerate(fields):
    region = regions[i]
    if options.verbose:
      print('region=', region)
    for disk in field:
      name = pool.take(used)
      if name is None:
        break
      used.add(name)
      im = Image.open(name)
      # check for exif data indicating the camera was rotated and correct for that
      base_angle = 0
      exif = im.getexif()
      if exif:
        r = exif.get(274, 1)
        if r == 6:
          base_angle = -90
        elif r == 8:
          base_angle = 90
          
      scale = 2*disk.radius*(1+options.overlap)*scaleup/math.hypot(im.size[0], im.size[1])
      im = im.resize((int(im.size[0]*scale),int(im.size[1]*scale)), Image.LANCZOS)
      angle = base_angle + random.uniform(-options.tilt, options.tilt)
      im = rotate(add_shadow(add_border(im,
                                        int(options.border*scaleup)),
                             int(options.shadow*scaleup)),
                  angle)
      isize = (im.size[0]/scaleup, im.size[1]/scaleup)
      x = disk.center.real - isize[0]/2
      y = disk.center.imag - isize[1]/2
      if x < 0:
        x = 0
      elif x + isize[0] > field.width:
        x = field.width - isize[0]
      if y < 0:
        y = 0
      elif y + isize[1] > field.height:
        y = field.height - isize[1]
      x += region[0]
      y += region[1]
      if options.verbose:
        print('placing %s at %d,%d' % (name, x, y))
      # coordinates are pixels in the saved image
      log.writerow([result_name, name,
                    int(x*options.scale), int(y*options.scale),
                    int(isize[0]*options.scale), int(isize[1]*options.scale),
                    '%.1f' % angle])
      x *= scaleup
      y *= scaleup
      out.paste(im, (int(x),int(y)), im)

  if scaledown != 1:
    if options.verbose:
      print('antialiasing')
    out = out.resize((int(out.size[0]/scaledown), int(out.size[1]/scaledown)),
                     Image.LANCZOS)
  return out

# load up some images
image_names = []
for dir_path, dirnames, filenames in os.walk(image_dir):
  for filename in filenames:
    base, ext = os.path.splitext(filename)
    if ext.lower() in ['.jpg', '.jpeg', '.gif', '.bmp', '.png']:
      image_names.append(os.path.join(dir_path, filename))
if options.verbose:
  print(len(image_names), 'images found')

# images already on kept screens, matched to this run's names so './a/b.jpg' and 'a/b.jpg' agree
kept_images = set(os.path.normpath(row['image']) for row in kept_rows)
already_used = set(name for name in image_names if os.path.normpath(name) in kept_images)
available = len(image_names) - len(already_used)
if options.keeps:
  print('%d images are on kept screens, %d left for this run' % (len(already_used), available))

if options.fit:
  if not available:
    parser.error('--fit needs at least one image in %s that is not on a kept screen' % image_dir)
  layouts, big, small = fit_layouts(available)
  message = '--big %.0f --small %.0f fits %d pictures for %d images (%s)' % (
    big, small, count_disks(layouts), available,
    ', '.join('%d on %s' % (sum(f.len() for f in fields), name)
              for fields, (size, regions, name) in zip(layouts, jobs)))
  print(message)
  if options.fit == 'suggest':
    sys.exit(0)
else:
  layouts = [ place_disks(regions, options.big, options.small) for size, regions, name in jobs ]

pool = ImagePool(image_names, already_used)

log_name = options.placement_log
if log_name is None:
  first_output = jobs[0][2] % dict(os.environ)
  stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
  log_name = os.path.join(os.path.dirname(first_output), 'montage-placements-%s.csv' % stamp)
else:
  log_name = log_name % dict(os.environ)

with open(log_name, 'w', newline='') as log_file:
  log = csv.writer(log_file)
  columns = ['output', 'image', 'x', 'y', 'width', 'height', 'angle']
  log.writerow(columns)
  # copy the kept screens so this log describes the whole set and can itself be kept from
  for row in kept_rows:
    log.writerow([ row[column] for column in columns ])
  for (size, regions, result_name), fields in zip(jobs, layouts):
    result_name = result_name % dict(os.environ)
    out = render(size, regions, fields, pool, result_name, log)
    if options.verbose:
      print('saving')
    out.save(result_name)
