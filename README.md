# Pywillparser
Python 3 library to convert Wacom .will files in SVG or InkML

The test files (test.will and multipage.will) have been generated using a Wacom Slate A5 and exported using the official
 Wacom Inkspace app (https://www.wacom.com/en/products/apps-services/inkspace)



## Usage

```
from willparser.willparser import WillParser

wp = WillParser()
wp.open('test.will')
wp.save_as_svg('output/test.svg')
wp.save_as_inkml('output/test.inkml')
wp.save_as_json('output/test.json')

# Multiple pages are saved in separated files. A number in the output file names
# indicates the page number
wp.open('multipage.will')
wp.save_as_svg('output/mp.svg', use_polyline=False)  # Set to true to use polyline instead of path for SVG
wp.save_as_inkml('output/mp.inkml')
wp.save_as_json('output/mp.json')

```
