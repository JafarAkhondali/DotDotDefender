import utils.tools
import unittest


class UtilTestCases(unittest.TestCase):
    def test_gh_url_to_raw(self):
        blob_style_url = 'https://github.com/jeros808/taa-dashboard-Basic-Crud-App/blob/6ead5e2e951274d8d7a51bb38cf509c5f01aa87c/no-node_modules/webpack-dev-server/lib/Server.js'
        head_style_url = 'https://raw.githubusercontent.com/jeros808/taa-dashboard-Basic-Crud-App/HEAD/no-node_modules/webpack-dev-server/lib/Server.js'

        formatted_head = utils.tools.gh_url_to_raw(blob_style_url)
        self.assertEqual(formatted_head, head_style_url)

    def test_gh_url_to_path(self):
        head_style_url = 'https://raw.githubusercontent.com/jeros808/taa-dashboard-Basic-Crud-App/HEAD/no-node_modules/webpack-dev-server/lib/Server.js'
        expected_path = '/no-node_modules/webpack-dev-server/lib/Server.js'
        extracted_path = utils.tools.gh_url_to_path(head_style_url)
        self.assertEqual(extracted_path, expected_path)

    def test_old_gh(self):
        blob_style_url = 'https://github.com/jeros808/taa-dashboard-Basic-Crud-App/blob/6ead5e2e951274d8d7a51bb38cf509c5f01aa87c/no-node_modules/webpack-dev-server/lib/Server.js'
        expected_path = '/no-node_modules/webpack-dev-server/lib/Server.js'
        url = blob_style_url[blob_style_url.index("blob") + 5:]
        extracted_path = url[url.index("/"):]
        self.assertEqual(extracted_path, expected_path)

if __name__ == '__main__':
    unittest.main()
