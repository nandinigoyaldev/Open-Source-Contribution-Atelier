from django.core.management.base import BaseCommand

from apps.rbac.models import Permission, Role



class Command(BaseCommand):
    help = "Seeds the database with base RBAC roles and permissions"

    def handle(self, *args, **options):
        # 1. Define Permissions
        permissions_data = [
            {"slug": "manage_roles", "description": "Can assign and revoke roles"},
            {"slug": "view_audit_logs", "description": "Can view RBAC audit logs"},
            {"slug": "manage_users", "description": "Can manage user accounts"},
            {
                "slug": "create_content",
                "description": "Can create learning modules and challenges",
            },
            {
                "slug": "moderate_content",
                "description": "Can moderate community content and forums",
            },
            {
                "slug": "review_prs",
                "description": "Can review and merge student pull requests",
            },
        ]

        permission_objs = {}
        for perm_data in permissions_data:
            perm, created = Permission.objects.get_or_create(
                slug=perm_data["slug"],
                defaults={"description": perm_data["description"]},
            )
            permission_objs[perm.slug] = perm
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created permission: {perm.slug}")
                )

        # 2. Define Roles and their Permissions
        roles_data = {
            "Administrator": [
                "manage_roles",
                "view_audit_logs",
                "manage_users",
                "create_content",
                "moderate_content",
                "review_prs",
            ],
            "Moderator": ["moderate_content", "manage_users"],
            "Content Creator": ["create_content"],
            "Mentor": ["review_prs", "moderate_content"],
            "Student": [],  # Base role, typically no special backend permissions
        }

        for role_name, perms in roles_data.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    "is_system_role": True,
                    "description": f"System role for {role_name}",
                },
            )

            # Assign permissions
            role.permissions.clear()
            for perm_slug in perms:
                role.permissions.add(permission_objs[perm_slug])

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {role.name}"))
            else:
                self.stdout.write(f"Updated role: {role.name}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded RBAC data!"))
