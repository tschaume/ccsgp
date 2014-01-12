"""
.. module:: classes
   :platform: Unix, Windows
   :synopsis: provides classes to use with ccsgp public functions

.. moduleauthor:: Patrick Huck <phuck@lbl.gov>
"""

import os, re
import Gnuplot, Gnuplot.funcutils
from subprocess import call
from itertools import izip
from utils import zip_flat
from config import basic_setup, default_margins, xPanProps

os.environ['GNUPLOT_PS_DIR'] = os.path.dirname(__file__)

class MyPlot(object):
  """base class for 1D and 2D plots

  - basic gnuplot setup (bars, grid, title, key, terminal, multiplot)
  - utility functions for general plotting

  :param title: image title
  :type title: str
  :param name: basename used for output files
  :type name: str
  :param debug: debug flag for verbose gnuplot output
  :type debug: bool
  """
  def __init__(self, name = 'test', title = '', debug = 0):
    self.name = name
    self.epsname = name + '.eps'
    self.gp = Gnuplot.Gnuplot(debug = debug)
    self.nPanels = 0
    self.nVertLines = 0
    self.nLabels = 0
    self.setter(['title "%s"' % title] + basic_setup)

  def _using(self, style):
    """determine string with columns to use

    :param style: gnuplot style
    :type style: str
    :returns: '1:2:3' or '1:2:3:4'
    """
    return '1:2:3' if style != 'boxerrorbars' else '1:2:3:4'

  def _plot_errs(self, data, style):
    """determine whether to plot errors separately

    :param data: one dataset
    :type data: numpy array of data points w/ format [x, y, dy, bw]
    :param style: corresponding gnuplot style
    :type style: str
    :returns: True or False
    """
    return (
      style != 'boxerrorbars' and style != 'yerrorbars' and
      data.T[2].sum() > 0
    )

  def _with_errs(self, prop):
    """generate special property string for errors

    - currently error bars are drawn in black
    - TODO: give user the option to draw error bars in lighter color according
      to the respective data points

    :param prop: property string of a dataset
    :type prop: str
    :returns: property string for errors
    """
    lw = re.compile('lw \d').search(prop).group()[-1]
    return 'yerrorbars pt 0 lt 1 lc 0 lw %s' % lw

  def initData(self, data, styles, properties, titles):
    """initialize the data

    - all lists given as parameters must have the same length.
    - supported gnuplot styles:
      points, lines, linespoints, yerrorbars, boxerrorbars
    - for the styles points, lines and linespoints each data set is drawn twice
      to allow for different colors for the errorbars
    - error bars use the same linewidth as data points and line color black

    :param data: data points w/ format [x, y, dy, bw] for each dataset 
    :type data: list of numpy arrays
    :param styles: plot styles for each dataset
    :type styles: list of str
    :param properties: plot properties for each dataset (pt/lw/ps/lc...)
    :type properties: list of str
    :param titles: key/legend titles for each dataset
    :type titles: list of strings
    """
    # dataSets used in hdf5()
    self.dataSets = { (k, v) for k, v in izip(titles, data) if k }
    # zip all input parameters for easier looping
    zipped = izip(data, styles, properties, titles)
    # uneven: main data points drawn second
    main_data = [
      Gnuplot.Data(
        d, inline = 1, title = t, using = _using(s), with_ = ' '.join([s, p])
      ) for d, s, p, t in zipped
    ]
    # even: secondary data doubled up to plot errors separately
    sec_data = [
      Gnuplot.Data(
        d, inline = 1, using = _using(s), with_ = _with_errs(p)
      ) if _plot_errs(d, s) else None for d, s, p, t in zipped
    ]
    # zip main & secondary data and filter out None's
    self.data = filter(None, zip_flat(main_data, sec_data))

  def setter(self, list):
    """convenience function to set a list of gnuplot options

    :param list: list of strings given to gnuplot's set command
    :type list: list
    """
    for s in list: self.gp('set %s' % s)

  def setMargins(self, **kwargs):
    """set the margins
    
    keys other than l, b, t, r are ignored (see config.default_margins)
    """
    self.setter([
      '%smargin %f' % (
        k, kwargs.get(k, default_margins[k])
      ) for k in default_margins
    ])

  def setAxisRange(self, rng, axis = 'x'):
    """set range for specified axis

    automatically determines axis range to include all data points if range is
    not given.

    :param rng: lower and upper range limits
    :type rng: list
    :param axis: axis to which to apply range
    :type axis: str
    """
    if rng is None:
      vals = [ n for v in self.data for n in v[:, 1] ]
      rng = [ min(vals), max(vals) ]
    self.gp('set %srange [%e:%e]' % (axis, rng[0], rng[1]))

  def setAxisLabel(self, label, axis = 'x'):
    """set label for specified axis

    :param label: label
    :type label: str
    :param axis: axis which to label
    :type axis: str
    """
    self.gp('set %slabel "%s"' % (axis, label))

  def setAxisLog(self, log, axis = 'x'):
    """set logarithmic scale for specified axis

    :param log: whether to set logarithmic
    :type log: bool
    :param axis: axis which to set logarithmic
    :type axis: str
    """
    if log:
      self.setter([
        'logscale %s' % axis, 'grid m%stics' % axis,
        'format {0} "10^{%L}"'.format(axis)
      ])
    else:
      self.gp('unset logscale %s' % axis)
      self.gp('set format {0} "%g"'.format(axis))

  def setVerticalLine(self, x, opts):
    """draw a vertical line

    :param x: position on x-axis
    :type x: float
    :param opts: line draw options
    :type opts: str
    """
    self.nVertLines += 1
    self.gp(
      'set arrow %d from %f,graph(0,0) to %f,graph(1,1) nohead %s' % (
        self.nVertLines, x, x, opts
      )
    )

  def setLabel(self, label, pos, abs_place = False):
    """draw a label into the figure

    :param label: label
    :type label: str
    :param pos: x,y - position
    :type pos: list
    :param abs_place: absolute or relative placement
    :type abs_place: bool
    """
    self.nLabels += 1
    place = 'at' if abs_place else 'at graph'
    self.gp(
      'set label %d "%s" %s %f, %f' % (
        self.nLabels, label, place, pos[0], pos[1]
      )
    )

  def convert(self):
    """convert eps original into pdf, png and jpg format"""
    call(' '.join([
      'ps2pdf -dEPSCrop', self.epsname, self.name + '.pdf'
    ]), shell = True)
    for ext in ['.png', '.jpg']:
      call(' '.join([
        'convert -density 150', self.name + '.pdf', self.name + ext
      ]), shell = True)

  def hdf5(self):
    """write data contained in plot to HDF5 file

    - easy numpy import -> (savetxt) -> gnuplot
    - export to ROOT objects

    h5py howto:
      - open file: `f = h5py.File(name, 'r')`
      - list datasets: `list(f)`
      - load entire dataset as np array: `arr = f['dst_name'][...]`
      - NOTE: literally type the 3 dots, replace dset_name
      - np.savetxt format: `fmt = '%.4f %.3e %.3e %.3e'`
      - save array to txt file: `np.savetxt('arr.dat', arr, fmt=fmt)`
    """
    try:
      import h5py
      f = h5py.File(self.name + '.hdf5', 'w')
      for k, v in self.dataSets: f.create_dataset(k, data = v)
      f.close()
    except ImportError:
      print 'install h5py to also save an hdf5 file of your plot!'
    except:
      print 'h5py imported but error raised!'
      raise

  def hardcopy(self):
    """generate eps, convert to other formats and write data to hdf5"""
    self.gp.hardcopy(
      self.epsname, enhanced = 1, color = 1, mode = 'landscape', fontsize = 24
    )
    self.convert()
    self.hdf5()

  def plot(self):
    """plot and generate output files"""
    self.gp.plot(*self.data)
    if self.nPanels < 1: self.hardcopy()


########################################################
## TODO: below are needed for multiplot and under dev ##
########################################################
#  def prepare_multiplot(self):
#    panel_setup = [
#      'terminal postscript eps enhanced color "Helvetica" 24',
#      'size %f,1' % xPanProps[0], 'output "%s"' % plt.epsname,
#      'multiplot'
#    ]
#    self.setter(panel_setup)
#
#  def prepare_subfig(self):
#    pan_wdth = xPanProps[1] * xPanProps[0]
#    xorig = xPanProps[2] + self.nPanels * pan_wdth
#    self.gp('set origin %f,0' % xorig)
#    self.gp('set size %f,1' % pan_wdth)
#    if self.nPanels > 0: self.gp('set ytics format " "')
#    self.nPanels += 1
#
########################################################
