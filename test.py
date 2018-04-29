from willparser.willparser import WillParser

wp = WillParser()
wp.open('test.will')
wp.save_as_svg('output/test.svg')
wp.save_as_inkml('output/test.inkml')
wp.save_as_json('output/test.json')

wp.open('multipage.will')
wp.save_as_svg('output/mp.svg', use_polyline=False)
wp.save_as_inkml('output/mp.inkml')
wp.save_as_json('output/mp.json')
