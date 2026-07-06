"""
Admin configuration for feature flags with A/B testing and advanced management.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """
    Advanced admin interface for FeatureFlag model.
    """
    
    # ============================================================
    # List Display Configuration
    # ============================================================
    
    list_display = (
        "name",
        "enabled_badge",
        "status_badge",
        "strategy_badge",
        "target_percentage",
        "exposure_count",
        "conversion_rate",
        "description_short",
        "created_at",
    )
    
    list_filter = (
        "enabled",
        "status",
        "strategy",
        "created_at",
    )
    
    search_fields = (
        "name",
        "description",
        "targeting_rules",
    )
    
    list_per_page = 50
    list_select_related = True
    date_hierarchy = "created_at"
    
    # ============================================================
    # Field Configuration
    # ============================================================
    
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "name",
                "description",
                "enabled",
                "status",
            ),
            "classes": ("wide",),
        }),
        ("Configuration", {
            "fields": (
                "strategy",
                "value",
                "variants",
            ),
            "classes": ("wide",),
        }),
        ("Targeting", {
            "fields": (
                "target_users",
                "target_roles",
                "target_percentage",
                "targeting_rules",
            ),
            "classes": ("wide",),
            "description": "Configure who should see this feature flag.",
        }),
        ("Analytics", {
            "fields": (
                "exposure_count",
                "enabled_count",
                "conversion_count",
                "stats_display",
            ),
            "classes": ("collapse", "wide"),
            "description": "Analytics and usage statistics for this flag.",
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
                "activated_at",
                "deactivated_at",
            ),
            "classes": ("collapse",),
        }),
    )
    
    readonly_fields = (
        "exposure_count",
        "enabled_count",
        "conversion_count",
        "stats_display",
        "created_at",
        "updated_at",
        "activated_at",
        "deactivated_at",
    )
    
    # ============================================================
    # Inline Models
    # ============================================================
    
    inlines = [
        # We'll add ExperimentInline later
    ]
    
    # ============================================================
    # Actions
    # ============================================================
    
    actions = [
        "enable_flags",
        "disable_flags",
        "activate_flags",
        "deactivate_flags",
        "archive_flags",
        "reset_analytics",
        "duplicate_flags",
    ]
    
    @admin.action(description="✅ Enable selected flags")
    def enable_flags(self, request, queryset):
        """Enable selected flags."""
        count = 0
        for flag in queryset:
            flag.enabled = True
            flag.save()
            count += 1
        self.message_user(request, f"✅ Enabled {count} flags.", messages.SUCCESS)
    
    @admin.action(description="❌ Disable selected flags")
    def disable_flags(self, request, queryset):
        """Disable selected flags."""
        count = 0
        for flag in queryset:
            flag.enabled = False
            flag.save()
            count += 1
        self.message_user(request, f"❌ Disabled {count} flags.", messages.WARNING)
    
    @admin.action(description="🚀 Activate selected flags")
    def activate_flags(self, request, queryset):
        """Activate selected flags."""
        count = 0
        for flag in queryset:
            flag.activate(request.user)
            count += 1
        self.message_user(request, f"🚀 Activated {count} flags.", messages.SUCCESS)
    
    @admin.action(description="⏹ Deactivate selected flags")
    def deactivate_flags(self, request, queryset):
        """Deactivate selected flags."""
        count = 0
        for flag in queryset:
            flag.deactivate(request.user)
            count += 1
        self.message_user(request, f"⏹ Deactivated {count} flags.", messages.WARNING)
    
    @admin.action(description="📦 Archive selected flags")
    def archive_flags(self, request, queryset):
        """Archive selected flags."""
        count = 0
        for flag in queryset:
            flag.archive(request.user)
            count += 1
        self.message_user(request, f"📦 Archived {count} flags.", messages.INFO)
    
    @admin.action(description="🔄 Reset analytics for selected flags")
    def reset_analytics(self, request, queryset):
        """Reset analytics counts for selected flags."""
        count = 0
        for flag in queryset:
            flag.exposure_count = 0
            flag.enabled_count = 0
            flag.conversion_count = 0
            flag.save()
            count += 1
        self.message_user(
            request, 
            f"🔄 Reset analytics for {count} flags.", 
            messages.INFO
        )
    
    @admin.action(description="📋 Duplicate selected flags")
    def duplicate_flags(self, request, queryset):
        """Duplicate selected flags with new names."""
        count = 0
        for flag in queryset:
            # Create duplicate
            new_flag = FeatureFlag.objects.create(
                name=f"{flag.name}_copy_{timezone.now().timestamp()}",
                description=f"Copy of {flag.name} - {flag.description}",
                enabled=False,
                strategy=flag.strategy,
                status=FeatureFlag.STATUS_DRAFT,
                value=flag.value,
                variants=flag.variants,
                target_percentage=flag.target_percentage,
                target_roles=flag.target_roles,
                targeting_rules=flag.targeting_rules,
            )
            # Copy many-to-many relationships
            new_flag.target_users.set(flag.target_users.all())
            count += 1
        self.message_user(
            request, 
            f"📋 Duplicated {count} flags (draft mode).", 
            messages.SUCCESS
        )
    
    # ============================================================
    # Custom Display Methods
    # ============================================================
    
    def enabled_badge(self, obj):
        """Display enabled status as a badge."""
        if obj.enabled:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">✅ Active</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">❌ Inactive</span>'
        )
    enabled_badge.short_description = "Status"
    
    def status_badge(self, obj):
        """Display status as a color-coded badge."""
        colors = {
            FeatureFlag.STATUS_DRAFT: '#6c757d',
            FeatureFlag.STATUS_ACTIVE: '#28a745',
            FeatureFlag.STATUS_INACTIVE: '#dc3545',
            FeatureFlag.STATUS_ARCHIVED: '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {0}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{1}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Lifecycle"
    
    def strategy_badge(self, obj):
        """Display strategy as a badge."""
        strategies = {
            FeatureFlag.STRATEGY_BOOLEAN: '⚪ Boolean',
            FeatureFlag.STRATEGY_PERCENTAGE: '📊 Percentage',
            FeatureFlag.STRATEGY_USER_WHITELIST: '✅ Whitelist',
            FeatureFlag.STRATEGY_USER_BLACKLIST: '🚫 Blacklist',
            FeatureFlag.STRATEGY_ROLE: '👤 Role',
            FeatureFlag.STRATEGY_CUSTOM: '⚙️ Custom',
        }
        return strategies.get(obj.strategy, obj.strategy)
    strategy_badge.short_description = "Strategy"
    
    def conversion_rate(self, obj):
        """Display conversion rate."""
        if obj.exposure_count > 0:
            rate = (obj.conversion_count / obj.exposure_count) * 100
            color = '#28a745' if rate > 50 else '#ffc107' if rate > 20 else '#dc3545'
            return format_html(
                '<span style="color: {0}; font-weight: bold;">{1:.1f}%</span>',
                color,
                rate
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    conversion_rate.short_description = "Conversion Rate"
    
    def description_short(self, obj):
        """Truncate description."""
        if len(obj.description) > 50:
            return obj.description[:50] + "..."
        return obj.description
    description_short.short_description = "Description"
    
    def stats_display(self, obj):
        """Display analytics statistics."""
        if obj.exposure_count == 0:
            return "No data yet"
        
        return format_html(
            """
            <div style="font-family: monospace;">
                <strong>📊 Analytics</strong><br>
                👁️ Exposures: <strong>{}</strong><br>
                ✅ Enabled: <strong>{}</strong><br>
                🎯 Conversions: <strong>{}</strong><br>
                📈 Rate: <strong>{:.1f}%</strong>
            </div>
            """,
            obj.exposure_count,
            obj.enabled_count,
            obj.conversion_count,
            (obj.conversion_count / obj.exposure_count * 100) if obj.exposure_count > 0 else 0
        )
    stats_display.short_description = "Statistics"
    
    # ============================================================
    # Save Methods
    # ============================================================
    
    def save_model(self, request, obj, form, change):
        """Save model with audit logging."""
        if not change:
            # Creating new flag
            obj.save()
            FeatureFlagAuditLog.objects.create(
                feature_flag=obj,
                user=request.user,
                action='create',
                changes={'name': obj.name, 'enabled': obj.enabled},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            self.message_user(
                request, 
                f"✅ Feature flag '{obj.name}' created successfully.", 
                messages.SUCCESS
            )
        else:
            # Updating existing flag
            old_obj = FeatureFlag.objects.get(pk=obj.pk)
            changes = {}
            for field in ['name', 'enabled', 'strategy', 'status', 'value', 'target_percentage']:
                if getattr(old_obj, field) != getattr(obj, field):
                    changes[field] = {
                        'old': getattr(old_obj, field),
                        'new': getattr(obj, field)
                    }
            
            obj.save()
            
            if changes:
                FeatureFlagAuditLog.objects.create(
                    feature_flag=obj,
                    user=request.user,
                    action='update',
                    changes=changes,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                self.message_user(
                    request, 
                    f"✅ Feature flag '{obj.name}' updated successfully.", 
                    messages.SUCCESS
                )
    
    def delete_model(self, request, obj):
        """Delete model with audit logging."""
        name = obj.name
        obj.delete()
        self.message_user(
            request, 
            f"🗑️ Feature flag '{name}' deleted.", 
            messages.WARNING
        )
    
    def delete_queryset(self, request, queryset):
        """Delete multiple models with audit logging."""
        count = queryset.count()
        names = list(queryset.values_list('name', flat=True))
        queryset.delete()
        self.message_user(
            request, 
            f"🗑️ Deleted {count} flags: {', '.join(names[:5])}" + 
            (f" and {count - 5} more..." if count > 5 else ""),
            messages.WARNING
        )
    
    # ============================================================
    # Custom Actions
    # ============================================================
    
    def get_actions(self, request):
        """Customize actions based on user permissions."""
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            # Remove destructive actions for non-superusers
            actions.pop('archive_flags', None)
            actions.pop('delete_selected', None)
        return actions


