import unittest
from collection.crawler import parse_page


class CrawlerTest(unittest.TestCase):
    def test_extracts_visible_text_and_links(self):
        page = parse_page(
            '<title>Waveguide</title><nav>Menu</nav><main>'
            '<a href="/x">Modes</a><script>noise</script>'
            '<style>.hidden {}</style><p>Optical propagation</p></main>'
        )
        self.assertEqual(page.title, "Waveguide")
        self.assertIn("Modes", page.text)
        self.assertIn("Optical propagation", page.text)
        self.assertNotIn("noise", page.text)
        self.assertNotIn("Menu", page.text)
        self.assertEqual(page.links, ["/x"])
