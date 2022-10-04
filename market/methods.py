from django.core.exceptions import ObjectDoesNotExist
from market.models import Market
import structlog
log = structlog.get_logger(__name__)
