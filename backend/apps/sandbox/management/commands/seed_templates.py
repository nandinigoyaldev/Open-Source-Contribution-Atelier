import uuid
from django.core.management.base import BaseCommand
from apps.sandbox.models import TemplateCategory, ProjectTemplate, TemplateFile


class Command(BaseCommand):
    help = "Seeds the database with starter project templates"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding templates...")

        # Categories
        frontend_cat, _ = TemplateCategory.objects.get_or_create(
            name="Frontend",
            defaults={"description": "Frontend frameworks and libraries"},
        )
        backend_cat, _ = TemplateCategory.objects.get_or_create(
            name="Backend", defaults={"description": "Backend frameworks and APIs"}
        )

        # React Template
        react_template, created = ProjectTemplate.objects.get_or_create(
            name="React Starter",
            defaults={
                "category": frontend_cat,
                "description": "A basic React 18 template with Vite and TailwindCSS.",
                "language": "javascript",
                "tags": ["react", "vite", "tailwind"],
                "is_official": True,
            },
        )

        if created:
            TemplateFile.objects.create(
                template=react_template,
                path="package.json",
                content='{\n  "name": "react-starter",\n  "private": true,\n  "version": "0.0.0",\n  "type": "module",\n  "scripts": {\n    "dev": "vite",\n    "build": "vite build",\n    "preview": "vite preview"\n  },\n  "dependencies": {\n    "react": "^18.2.0",\n    "react-dom": "^18.2.0"\n  },\n  "devDependencies": {\n    "@types/react": "^18.2.15",\n    "@types/react-dom": "^18.2.7",\n    "@vitejs/plugin-react": "^4.0.3",\n    "vite": "^4.4.5"\n  }\n}\n',
            )
            TemplateFile.objects.create(
                template=react_template,
                path="index.html",
                content='<!DOCTYPE html>\n<html lang="en">\n  <head>\n    <meta charset="UTF-8" />\n    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n    <title>Vite + React</title>\n  </head>\n  <body>\n    <div id="root"></div>\n    <script type="module" src="/src/main.jsx"></script>\n  </body>\n</html>\n',
            )
            TemplateFile.objects.create(
                template=react_template,
                path="src/main.jsx",
                content='import React from "react"\nimport ReactDOM from "react-dom/client"\nimport App from "./App.jsx"\n\nReactDOM.createRoot(document.getElementById("root")).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>,\n)\n',
            )
            TemplateFile.objects.create(
                template=react_template,
                path="src/App.jsx",
                content='import React from "react"\n\nfunction App() {\n  return (\n    <div>\n      <h1>Hello React!</h1>\n      <p>Start editing to see some magic happen!</p>\n    </div>\n  )\n}\n\nexport default App\n',
            )

        # Python Template
        python_template, created = ProjectTemplate.objects.get_or_create(
            name="Python Starter",
            defaults={
                "category": backend_cat,
                "description": "A simple Python project.",
                "language": "python",
                "tags": ["python", "backend"],
                "is_official": True,
            },
        )

        if created:
            TemplateFile.objects.create(
                template=python_template,
                path="main.py",
                content='def main():\n    print("Hello from Python!")\n\nif __name__ == "__main__":\n    main()\n',
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded templates"))
