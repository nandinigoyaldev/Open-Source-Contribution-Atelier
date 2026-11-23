# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportCallIssue=false
import re

from django.db import IntegrityError, transaction
from rest_framework import serializers

from . import oidc_client
from .models import OrganizationOIDCProvider, OrganizationSSODomain
from .sso_service import PUBLIC_EMAIL_DOMAINS

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
MAX_DOMAINS = 20


class DomainListField(serializers.ListField):
    """Accepts a list of domain names, shows the provider's claimed domains."""

    def get_attribute(self, instance):
        return [d.domain for d in instance.domains.all()]


class OIDCProviderSerializer(serializers.ModelSerializer):
    """
    Per-organization OIDC settings. ``client_secret`` can be written but is never
    returned: the response only says whether one is stored.
    """

    client_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )
    has_client_secret = serializers.SerializerMethodField()
    domains = DomainListField(
        child=serializers.CharField(max_length=253),
        required=False,
        max_length=MAX_DOMAINS,
    )

    class Meta:
        model = OrganizationOIDCProvider
        fields = [
            "issuer",
            "client_id",
            "client_secret",
            "has_client_secret",
            "is_enabled",
            "auto_provision",
            "domains",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_has_client_secret(self, obj) -> bool:
        return bool(obj.client_secret)

    def validate_issuer(self, value):
        try:
            return oidc_client.check_url_syntax(value.strip(), what="issuer")
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_client_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("client_id is required")
        return value

    def validate_domains(self, value):
        cleaned = []
        for raw in value:
            domain = raw.strip().lower().lstrip("@")
            if not DOMAIN_RE.match(domain):
                raise serializers.ValidationError(f"'{raw}' is not a valid domain")
            if domain in PUBLIC_EMAIL_DOMAINS:
                raise serializers.ValidationError(
                    f"'{domain}' is a public email domain and can not be claimed"
                )
            if domain not in cleaned:
                cleaned.append(domain)
        provider = self.instance
        taken = OrganizationSSODomain.objects.filter(domain__in=cleaned)
        if provider is not None:
            taken = taken.exclude(provider=provider)
        clash = taken.values_list("domain", flat=True).first()
        if clash:
            raise serializers.ValidationError(
                f"'{clash}' is already used by another organization"
            )
        return cleaned

    def validate(self, attrs):
        if self.instance is None:
            for field in ("issuer", "client_id"):
                if field not in attrs:
                    raise serializers.ValidationError(
                        {field: "This field is required."}
                    )
        enabled = attrs.get(
            "is_enabled", self.instance.is_enabled if self.instance else False
        )
        domains = attrs.get(
            "domains",
            [d.domain for d in self.instance.domains.all()] if self.instance else [],
        )
        if enabled and not domains:
            raise serializers.ValidationError(
                {"domains": "Add at least one email domain before enabling SSO."}
            )
        return attrs

    def save(self, *, organization, **kwargs):
        domains = self.validated_data.pop("domains", None)
        try:
            with transaction.atomic():
                provider = super().save(organization=organization, **kwargs)
                if domains is not None:
                    provider.domains.exclude(domain__in=domains).delete()
                    have = set(provider.domains.values_list("domain", flat=True))
                    OrganizationSSODomain.objects.bulk_create(
                        [
                            OrganizationSSODomain(provider=provider, domain=d)
                            for d in domains
                            if d not in have
                        ]
                    )
        except IntegrityError:
            # Another organization claimed the same domain at the same moment.
            raise serializers.ValidationError(
                {"domains": "One of these domains is already in use."}
            )
        return provider
