import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PUBLIC_DIR = path.resolve(__dirname, "../public");
const CONTENT_DIR = path.join(PUBLIC_DIR, "content");
const CURRICULUM_PATH = path.join(CONTENT_DIR, "curriculum.json");
const OUTPUT_PATH = path.join(PUBLIC_DIR, "search_index.json");

function stripMarkdown(text) {
  if (!text) return "";
  return text
    .replace(/[#*`_\[\]()]/g, " ") // Remove markdown characters
    .replace(/\s+/g, " ") // Collapse whitespace
    .trim();
}

function generateIndex() {
  console.log("Generating search index...");

  if (!fs.existsSync(CURRICULUM_PATH)) {
    console.warn(`Curriculum not found at ${CURRICULUM_PATH}`);
    return;
  }

  const curriculum = JSON.parse(fs.readFileSync(CURRICULUM_PATH, "utf-8"));
  const index = [];
  let blockId = 0;

  for (const module of curriculum.modules || []) {
    for (const lesson of module.lessons || []) {
      // Index the lesson title and description
      index.push({
        id: `idx-${blockId++}`,
        slug: lesson.slug,
        title: lesson.title,
        subtitle: module.title,
        content: lesson.description || "",
        type: "lesson",
        hash: "",
      });

      // If there's a markdown file, parse it for headings and content
      if (lesson.filePath) {
        const mdPath = path.join(CONTENT_DIR, lesson.filePath);
        if (fs.existsSync(mdPath)) {
          const mdContent = fs.readFileSync(mdPath, "utf-8");
          const lines = mdContent.split("\n");

          let currentHeading = "";
          let currentHash = "";
          let paragraphBuffer = [];

          const flushParagraph = () => {
            const content = stripMarkdown(paragraphBuffer.join(" "));
            if (content.length > 10) {
              // Only index substantial text
              index.push({
                id: `idx-${blockId++}`,
                slug: lesson.slug,
                title: lesson.title,
                subtitle: currentHeading || lesson.title,
                content: content,
                type: "content",
                hash: currentHash,
              });
            }
            paragraphBuffer = [];
          };

          for (const line of lines) {
            const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
            if (headingMatch) {
              flushParagraph();
              currentHeading = headingMatch[2].trim();
              // Generate a simple anchor hash (similar to what typical markdown parsers do)
              currentHash = currentHeading
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/(^-|-$)/g, "");

              index.push({
                id: `idx-${blockId++}`,
                slug: lesson.slug,
                title: lesson.title,
                subtitle: "Heading",
                content: currentHeading,
                type: "heading",
                hash: currentHash,
              });
            } else {
              paragraphBuffer.push(line);
            }
          }
          flushParagraph();
        }
      }
    }
  }

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(index, null, 2));
  console.log(
    `Successfully generated search index with ${index.length} entries at ${OUTPUT_PATH}`,
  );
}

generateIndex();
