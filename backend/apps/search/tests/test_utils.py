from django.test import TestCase
from apps.search.utils import extract_searchable_text

class SearchUtilsTestCase(TestCase):
    def test_extract_searchable_text_with_code_blocks(self):
        markdown_content = """
        # Lesson Title
        This is a normal paragraph with an inline `<div>` code snippet.
        
        ```html
        <div class="test-class">
            <p>Unescaped raw HTML snippet inside a code block</p>
        </div>
        ```
        
        End of lesson description.
        """
        
        extracted = extract_searchable_text(markdown_content)
        
        # Verify that unescaped HTML tags inside code blocks were stripped/handled safely
        self.assertIn("Lesson Title", extracted)
        self.assertIn("normal paragraph", extracted)
        self.assertNotIn("class=\"test-class\"", extracted)
        self.assertIn("End of lesson description.", extracted)
