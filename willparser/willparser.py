"""Converts Wacom Spark/Slate .will files in different formats

"""

__author__ = "Giovanni Iovino"
__copyright__ = "Copyright 2018, Giovanni Iovino"
__license__ = "MIT"
__maintainer__ = "Giovanni Iovino"
__email__ = "giovanni.iovino.dev@gmail.com"
__status__ = "Development"

from willparser.wacompath import Path
import numpy
import zipfile
import xmltodict
import os
import json


class _WillPage:
    """
    Object holding data of each page found in a .will file
    """

    def __init__(self, paths, width=592, height=864):
        self.paths = paths
        self.width = str(width)
        self.height = str(height)


class CurveUtil:
    """Utility class than can be used to generate Catmull-Rom and Bezier curves from an array of points
    """
    alpha = 0.5

    def __init__(self):
        pass

    @staticmethod
    def get_t(ti, pi, pj):
        xi, yi = pi
        xj, yj = pj
        return (((xj - xi) ** 2 + (yj - yi) ** 2) ** 0.5) ** CurveUtil.alpha + ti

    @staticmethod
    def __catmull_rom_spline(p0, p1, p2, p3, npoints=2):
        """
        P0, P1, P2, and P3 should be (x,y) point pairs that define the Catmull-Rom spline.
        nPoints is the number of points to include in this curve segment.
        @source: https://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
        """
        # Convert the points to numpy so that we can do array multiplication
        p0, p1, p2, p3 = map(numpy.array, [p0, p1, p2, p3])

        # Calculate t0 to t4

        t0 = 0
        t1 = CurveUtil.get_t(t0, p0, p1)
        t2 = CurveUtil.get_t(t1, p1, p2)
        t3 = CurveUtil.get_t(t2, p2, p3)

        # Only calculate points between P1 and P2
        t = numpy.linspace(t1, t2, npoints)

        # Reshape so that we can multiply by the points P0 to P3
        # and get a point for each value of t.
        t = t.reshape(len(t), 1)
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3

        c = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
        if numpy.isnan(c).any():
            c = [p0, p1, p2, p3]
        return c

    @staticmethod
    def catmull_rom_chain(points):
        """Calculate Catmull Rom for a chain of points and return the combined curve.
        @source: https://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
        """
        sz = len(points)

        # The curve C will contain an array of (x,y) points.
        c = []
        for i in range(sz - 3):
            _p = CurveUtil.__catmull_rom_spline(points[i], points[i + 1], points[i + 2], points[i + 3])
            c.extend(_p)

        return c

    @staticmethod
    def __bezier(p0, p1, p2, p3):
        """Convert a Catmull-Rom segment to a Bezier curve
        :param p0: point [x,y]
        :param p1: point [x,y]
        :param p2: point [x,y]
        :param p3: point [x,y]
        :return: Array of Bezier points
        """
        p0, p1, p2, p3 = map(numpy.array, [p0, p1, p2, p3])

        t0 = 0.0
        t1 = CurveUtil.get_t(t0, p0, p1)
        t2 = CurveUtil.get_t(t1, p1, p2)
        t3 = CurveUtil.get_t(t2, p2, p3)

        c1 = (t2 - t1) / (t2 - t0)
        c2 = (t1 - t0) / (t2 - t0)
        d1 = (t3 - t2) / (t3 - t1)
        d2 = (t2 - t1) / (t3 - t1)
        m1 = (t2 - t1) * (c1 * (p1 - p0) / (t1 - t0) + c2 * (p2 - p1) / (t2 - t1))
        m2 = (t2 - t1) * (d1 * (p2 - p1) / (t2 - t1) + d2 * (p3 - p2) / (t3 - t2))
        q0 = p1
        q1 = (p1 + m1 / 3)
        q2 = (p2 - m2 / 3)
        if numpy.isnan(q1).any():
            q1 = p1
        if numpy.isnan(q2).any():
            q1 = p2
        q3 = p2
        bp = [q0, q1, q2, q3]

        return bp

    @staticmethod
    def bezier_chain(points):
        """Calculate Bezier for a chain of points and return the combined curve.
        :param points:
        :return:
        """

        chain = []
        for i in range(len(points) - 3):
            c = CurveUtil.__bezier(points[i], points[i + 1], points[i + 2], points[i + 3])
            chain.append(c)

        return numpy.array(chain)


class WillParser:
    """Parser class for .will files, allows reading of .will files and conversion to SVG and InkML format.
    """
    def __init__(self):
        """Constructor
        """
        self.pages = []
        self.filename = None

    def open(self, fname):
        """Open a .will file and read its content. Each section of the file will be stored in self.pages
        :param fname: File name
        """
        self.pages = []
        self.filename = fname
        _will = zipfile.ZipFile(fname)

        # Reads .rels file to collect saved pages
        _f = _will.open('_rels/.rels', 'r')
        _rels_content = _f.read()
        _f.close()
        _rels = xmltodict.parse(_rels_content)
        for _r in _rels['Relationships']['Relationship']:

            if _r['@Type'] == 'http://schemas.willfileformat.org/2015/relationships/section':
                _svg = os.path.split(_r['@Target'])[1]
                _s_rel_path = 'sections/_rels/' + _svg + '.rels'
                _s_rel_f = _will.open(_s_rel_path)
                _s_rel_content = _s_rel_f.read()
                _s_rel_f.close()
                _s_rel = xmltodict.parse(_s_rel_content)
                _proto_file = 'sections/media/' + os.path.split(_s_rel['Relationships']['Relationship']['@Target'])[1]
                # Reads page properties from svg section file
                _f = _will.open('sections/' + _svg)
                _svg_content = _f.read()
                _f.close()
                _svg_data = xmltodict.parse(_svg_content)
                _width = _svg_data.get('svg', {}).get('@width', 592)
                _height = _svg_data.get('svg', {}).get('@height', 864)
                # Reads data from protobuf file associated to the svg section file
                _f = _will.open(_proto_file)
                _content = _f.read()
                _f.close()
                _paths = self.__read_will_paths(_content)
                self.pages.append(_WillPage(_paths, _width, _height))

    def save_as_json(self, fname=None):
        """Save the parsed .will file in a JSON file
        Each section of the input file will be saved on a separated JSON file.
        :param fname: Output file name
        """
        _fname = self.filename
        if fname is not None:
            _fname = os.path.splitext(fname)[0]

        _pages = []
        for page in self.pages:

            _j_page = {
                'paths': page.paths,
                'width': page.width,
                'height': page.height
            }
            _pages.append(_j_page)

        _f = open(_fname + ".json", "w")
        _f.write(json.dumps(_pages, indent=4))
        _f.close()

    def save_as_svg(self, fname=None, use_polyline=False):
        """Save the parsed .will file in a SVG file
        Each section of the input file will be saved on a separated SVG file.
        :param fname: Output file name
        :param use_polyline: Set to true if you want to use svg polylines instead of svg paths during conversion
        """
        _fname = self.filename
        if fname is not None:
            _fname = os.path.splitext(fname)[0]
        __page_n = 0
        for page in self.pages:
            p_dict = {
                "svg": {
                    "@width": str(page.width),
                    "@height": str(page.height),
                    "polyline": [],
                    "path": []
                }
            }

            for path in page.paths:
                pth_dict = {
                    "@style": 'fill:none;stroke:black;stroke-width:' + str(path['avg_width'])
                }

                if use_polyline:
                    _data = ""
                    for p in path['points']:
                        _data += str(p[0]) + "," + str(p[1]) + " "
                    pth_dict['@points'] = _data
                    p_dict['svg']['polyline'].append(pth_dict)
                else:

                    _data = ""
                    _first = True
                    for p in path['points']:
                        if _first:
                            _data += "M" + str(p[0]) + " " + str(p[1])
                            _first = False
                        else:
                            _data += " L" + str(p[0]) + " " + str(p[1])
                    pth_dict['@d'] = _data
                    p_dict['svg']['path'].append(pth_dict)

            _f = open(_fname + str(__page_n) + ".svg", "w")
            _f.write(xmltodict.unparse(p_dict, pretty=True))
            _f.close()
            __page_n += 1

    def save_as_inkml(self, fname=None):
        """Save the parsed .will file in a InkML file
        InkML specs: https://www.w3.org/TR/InkML/
        Each section of the input file will be saved on a separated .inkml file.
        :param fname: Output file name
        """
        _fname = self.filename
        if fname is not None:
            _fname = os.path.splitext(fname)[0]

        _p_dict = {
            'inkml:ink': {
                '@xmlns:emma': 'http://www.w3.org/2003/04/emma',
                '@xmlns:msink': 'http://schemas.microsoft.com/ink/2010/main',
                '@xmlns:inkml': 'http://www.w3.org/2003/InkML',
                'inkml:definitions': {
                    'inkml:context': {
                        '@xml:id': 'ctxCoordinatesWithPressure',
                        'inkml:inkSource': {
                            '@xml:id': 'inkSrcCoordinatesWithPressure',
                            'inkml:traceFormat': {
                                'inkml:channel': [
                                    {
                                        '@name': 'X',
                                        '@type': 'integer',
                                        '@max': 32767,
                                        '@units': 'himetric'
                                    },
                                    {
                                        '@name': 'Y',
                                        '@type': 'integer',
                                        '@max': 32767,
                                        '@units': 'himetric'
                                    },
                                    {
                                        '@name': 'F',
                                        '@type': 'integer',
                                        '@max': 32767,
                                        '@units': 'dev'
                                    }
                                ]
                            },
                            'inkml:channelProperties': {
                                'inkml:channelProperty': [
                                    {
                                        '@channel': 'X',
                                        '@name': 'resolution',
                                        '@value': 1,
                                        '@units': '1/himetric'
                                    },
                                    {
                                        '@channel': 'Y',
                                        '@name': 'resolution',
                                        '@value': 1,
                                        '@units': '1/himetric'
                                    },
                                    {
                                        '@channel': 'F',
                                        '@name': 'resolution',
                                        '@value': 1,
                                        '@units': '1/dev'
                                    }
                                ]
                            }
                        }
                    },
                    'inkml:brush': {
                        '@xml:id': 'br0',
                        'inkml:brushProperty': [
                            {
                                '@name': 'width',
                                '@value': 100,
                                '@units': 'himetric'
                            },
                            {
                                '@name': 'height',
                                '@value': 100,
                                '@units': 'himetric'
                            },
                            {
                                '@name': 'color',
                                '@value': '#000000'
                            },
                            {
                                '@name': 'transparency',
                                '@value': 0
                            },
                            {
                                '@name': 'tip',
                                '@value': 'ellipse'
                            },
                            {
                                '@name': 'rasterOp',
                                '@value': 'copyPen'
                            },
                            {
                                '@name': 'ignorePressure',
                                '@value': False
                            },
                            {
                                '@name': 'antiAliased',
                                '@value': True
                            },
                            {
                                '@name': 'fitToCurve',
                                '@value': False
                            }
                        ]
                    }
                },
                'inkml:traceGroup': {
                    'inkml:trace': []
                }
            }
        }
        __page_n = 0
        for page in self.pages:
            __i = 0
            for path in page.paths:
                _t_dict = {
                    '@xml:id': 'trace_' + str(__i),
                    '@contextRef': '#ctxCoordinatesWithPressure',
                    '@brushRef': '#br0'
                }
                _data = ""
                __j = 0
                __l = len(path['points']) - 1
                for p in path['points']:
                    _data += str(int(p[0] * 26.45833)) + " " + str(int(p[1] * 26.45833)) + " " + str(path['avg_width']*1000)
                    if __j < __l:
                        _data += ","
                    __j += 1
                _t_dict['#text'] = _data
                _p_dict['inkml:ink']['inkml:traceGroup']['inkml:trace'].append(_t_dict)
                __i += 1

            _f = open(_fname + str(__page_n) + ".inkml", "w")
            _f.write(xmltodict.unparse(_p_dict))
            _f.close()
            __page_n += 1

    def __read_will_paths(self, payload):
        """
        Used to read  paths object from a will file protobuf section. Protobuf3 for python doesn't seems to handle correctly
        packed values, so this method provides an internal implementation for decoding a bytes payload
        :param payload: the protobuf content to parse
        :return: a list of Path objects
        """
        _l = 0
        __l = 0
        _paths = []
        __i = 0
        for b in payload:
            if _l == 0:
                if (b & 0x80) == 0x80:
                    __l += (b & 0x7F) << (7 * __i)
                    __i += 1
                else:
                    __l += (b & 0x7F) << (7 * __i)
                    _paths.append([])  # new path
                    _l = __l
            else:
                __i = 0
                __l = 0
                _paths[len(_paths) - 1].append(b)
                _l -= 1

        # Parse binary paths
        ret_paths = []
        for _pth in _paths:
            p = Path()
            p.parse_from_bytes(_pth)

            ints = self.__read_packed_sint32(p.points)
            points = self.__decode_will_coordinates(ints, p.decimalPrecision)

            strokes = self.__read_packed_sint32(p.strokeWidths)
            strokes = self.__decode_delta_encoded(strokes, p.decimalPrecision)
            _w = numpy.average(numpy.array(strokes))
            color = self.__read_packed_sint32(p.strokeColor)

            _path_dict = {
                "points": points,
                "strokes": strokes,
                "avg_width": _w,
                "color": color,
            }
            ret_paths.append(_path_dict)

        return ret_paths

    def __read_packed_sint32(self, payload):
        """
        Converts a bytes payload containing sint32 values and compliant to protobuf2 to a list of signed int values.
        Protobuf3 for python doesn't seems to handle correctly
        packed values, so this method provides an internal implementation for decoding a bytes payload
        :param payload: the protobuf content to parse
        :return:
        """
        _ints = []
        __l = 0
        __i = 0
        for _b in payload:
            if (_b & 0x80) == 0x80:
                __l += (_b & 0x7F) << (7 * __i)
                __i += 1
            else:
                __l += (_b & 0x7F) << (7 * __i)
                _n = (__l >> 1) ^ -(__l & 1)  # protobuf sint32 zigzag decode
                _ints.append(_n)
                __l = 0
                __i = 0
        return _ints

    def __decode_will_coordinates(self, _ints, _precision):
        """
        Used to decode coordinates from .will data-format as defined in
        https://developer-docs.wacom.com/display/DevDocs/WILL+Data+Format
        :param _ints: list of integer values
        :param _precision: decimal position for conversion to float
        :return: a list of converted float values
        """
        _l = int(len(_ints) / 2)
        _p = pow(10, _precision)
        _points = [[_ints[0], _ints[1]]]
        _i = 2
        for i in range(2, _l):
            _points.append([(_points[i - 2][0] + _ints[_i]), (_points[i - 2][1] + _ints[_i + 1])])
            _i += 2
        for i in range(0, len(_points)):
            _points[i][0] = _points[i][0] / _p
            _points[i][1] = _points[i][1] / _p

        return _points

    def __decode_delta_encoded(self, _ints, _precision):
        """
        Used handle delta encoding as defined in
        https://developer-docs.wacom.com/display/DevDocs/WILL+Data+Format
        :param _ints: list of integer values
        :param _precision: decimal position for conversion to float
        :return: a list of converted float values
        """
        _p = pow(10, _precision)

        for i in range(1, len(_ints)):
            _ints[i] = _ints[i - 1] + _ints[i]
        for i in range(0, len(_ints)):
            _ints[i] = _ints[i] / _p

        return _ints
