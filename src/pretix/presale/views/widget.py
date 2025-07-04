#
# This file is part of pretix (Community Edition).
#
# Copyright (C) 2014-2020 Raphael Michel and contributors
# Copyright (C) 2020-2021 rami.io GmbH and contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation in version 3 of the License.
#
# ADDITIONAL TERMS APPLY: Pursuant to Section 7 of the GNU Affero General Public License, additional terms are
# applicable granting you additional permissions and placing additional restrictions on your usage of this software.
# Please refer to the pretix LICENSE file to obtain the full terms applicable to this work. If you did not receive
# this file, see <https://pretix.eu/about/en/license>.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along with this program.  If not, see
# <https://www.gnu.org/licenses/>.
#
import calendar
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import isoweek
from compressor.filters.jsmin import rJSMinFilter
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.template import Context, Engine
from django.template.loader import get_template
from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import get_language, gettext, pgettext
from django.utils.translation.trans_real import DjangoTranslation
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import condition
from django.views.i18n import (
    JavaScriptCatalog, get_formats, js_catalog_template,
)
from lxml import html

from pretix.base.context import get_powered_by
from pretix.base.i18n import language
from pretix.base.models import (
    CartPosition, Event, ItemVariation, Quota, SubEvent, Voucher,
)
from pretix.base.services.cart import error_messages
from pretix.base.services.placeholders import PlaceholderContext
from pretix.base.settings import GlobalSettingsObject
from pretix.base.templatetags.rich_text import rich_text
from pretix.helpers.daterange import daterange
from pretix.helpers.thumb import get_thumbnail
from pretix.multidomain.urlreverse import build_absolute_uri
from pretix.presale.forms.organizer import meta_filtersets
from pretix.presale.style import get_theme_vars_css
from pretix.presale.views.cart import get_or_create_cart_id
from pretix.presale.views.event import (
    get_grouped_items, item_group_by_category,
)
from pretix.presale.views.organizer import (
    EventListMixin, add_events_for_days, add_subevents_for_days,
    days_for_template, filter_qs_by_attr, weeks_for_template,
)

logger = logging.getLogger(__name__)

# we never change static source without restart, so we can cache this thread-wise
_source_cache_key = None

version_min = 2
version_max = 2
version_default = 2  # used for output in widget-embed-code


def _get_source_cache_key(version):
    global _source_cache_key
    checksum = hashlib.sha256()
    if not _source_cache_key:
        with open(finders.find("pretixbase/scss/_theme_variables.scss"), "r") as f:
            checksum.update(f.read().encode())

        template_path = 'pretixpresale/widget_dummy.html' if version == version_max else 'pretixpresale/widget_dummy.v{}.html'.format(version)

        tpl = get_template(template_path)
        et = html.fromstring(tpl.render()).xpath('/html/head/link')[0].attrib['href'].replace(settings.STATIC_URL, '')
        checksum.update(et.encode())
        _source_cache_key = checksum.hexdigest()[:12]
    return _source_cache_key


def indent(s):
    return s.replace('\n', '\n  ')


def widget_css_etag(request, version, **kwargs):
    if version < version_min:
        version = version_min
    # This makes sure a new version of the theme is loaded whenever settings or the source files have changed
    if hasattr(request, 'event'):
        return (f'{_get_source_cache_key(version)}-'
                f'{request.organizer.cache.get_or_set("css_version", default=lambda: int(time.time()))}-'
                f'{request.event.cache.get_or_set("css_version", default=lambda: int(time.time()))}')
    else:
        return f'{_get_source_cache_key(version)}-{request.organizer.cache.get_or_set("css_version", default=lambda: int(time.time()))}'


def widget_js_etag(request, version, lang, **kwargs):
    gs = GlobalSettingsObject()
    return gs.settings.get('widget_checksum_{}_{}'.format(version, lang))


@gzip_page
@condition(etag_func=widget_css_etag)
@cache_page(60)
def widget_css(request, version, **kwargs):
    if version > version_max:
        raise Http404()
    if version < version_min:
        version = version_min
    o = getattr(request, 'event', request.organizer)

    template_path = 'pretixpresale/widget_dummy.html' if version == version_max else 'pretixpresale/widget_dummy.v{}.html'.format(version)

    tpl = get_template(template_path)
    et = html.fromstring(tpl.render()).xpath('/html/head/link')[0].attrib['href'].replace(settings.STATIC_URL, '')
    with open(finders.find(et), 'r') as f:
        widget_css = f.read()

    theme_css = get_theme_vars_css(o, widget=True)
    css = f"/* v{version} */\n" + theme_css + widget_css

    resp = FileResponse(css, content_type='text/css')
    resp._csp_ignore = True
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


def generate_widget_js(version, lang):
    code = []
    with language(lang):
        # Provide isolation
        code.append('(function (siteglobals) {\n')
        code.append('var module = {}, exports = {};\n')
        code.append('var lang = "%s";\n' % lang)

        c = JavaScriptCatalog()
        c.translation = DjangoTranslation(lang, domain='djangojs')
        catalog, plural = c.get_catalog(), c.get_plural()

        str_wl = (
            'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su',
            'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
            'September', 'October', 'November', 'December'
        )
        catalog = dict((k, v) for k, v in catalog.items() if k.startswith('widget\u0004') or k in str_wl)
        template = Engine().from_string(js_catalog_template)
        context = Context({
            'catalog_str': indent(json.dumps(
                catalog, sort_keys=True, indent=2)) if catalog else None,
            'formats_str': indent(json.dumps(
                get_formats(), sort_keys=True, indent=2)),
            'plural': plural,
        })
        i18n_js = template.render(context)
        i18n_js = i18n_js.replace('for (const ', 'for (var ')  # remove if we really want to break IE11 for good
        i18n_js = i18n_js.replace(r"value.includes(", r"-1 != value.indexOf(")  # remove if we really want to break IE11 for good
        code.append(i18n_js)

        files = [
            'vuejs/vue.js' if settings.DEBUG else 'vuejs/vue.min.js',
            'pretixpresale/js/widget/docready.js',
            'pretixpresale/js/widget/floatformat.js',
            'pretixpresale/js/widget/widget.js' if version == version_max else 'pretixpresale/js/widget/widget.v{}.js'.format(version),
        ]
        for fname in files:
            f = finders.find(fname)
            with open(f, 'r', encoding='utf-8') as fp:
                code.append(fp.read())

        if settings.DEBUG:
            code.append('})(this);\n')
        else:
            # Do not expose debugging variables
            code.append('})({});\n')
    code = ''.join(code)
    code = rJSMinFilter(content=code).output()
    return f"/* v{version} */\n" + code


@gzip_page
@condition(etag_func=widget_js_etag)
def widget_js(request, version, lang, **kwargs):
    if version > version_max or lang not in [lc for lc, ll in settings.LANGUAGES]:
        raise Http404()

    if version < version_min:
        version = version_min

    cached_js = cache.get('widget_js_data_v{}_{}'.format(version, lang))
    if cached_js and not settings.DEBUG:
        resp = HttpResponse(cached_js, content_type='text/javascript')
        resp._csp_ignore = True
        resp['Access-Control-Allow-Origin'] = '*'
        return resp

    gs = GlobalSettingsObject()
    fname = gs.settings.get('widget_file_{}_{}'.format(version, lang))
    resp = None
    if fname and not settings.DEBUG:
        if isinstance(fname, File):
            fname = fname.name
        try:
            data = default_storage.open(fname).read()
            resp = HttpResponse(data, content_type='text/javascript')
            cache.set('widget_js_data_v{}_{}'.format(version, lang), data, 3600 * 4)
        except:
            logger.exception('Failed to open widget.js')

    if not resp:
        data = generate_widget_js(version, lang).encode()
        checksum = hashlib.sha1(data).hexdigest()
        if not settings.DEBUG:
            newname = default_storage.save(
                'widget/widget.{}.{}.{}.js'.format(version, lang, checksum),
                ContentFile(data)
            )
            gs.settings.set('widget_file_{}_{}'.format(version, lang), 'file://' + newname)
            gs.settings.set('widget_checksum_{}_{}'.format(version, lang), checksum)
            cache.set('widget_js_data_v{}_{}'.format(version, lang), data, 3600 * 4)
        resp = HttpResponse(data, content_type='text/javascript')
    resp._csp_ignore = True
    resp['Access-Control-Allow-Origin'] = '*'
    return resp


def price_dict(item, price):
    return {
        'gross': price.gross,
        'net': price.net,
        'tax': price.tax,
        'rate': price.rate,
        'name': str(price.name),
        'includes_mixed_tax_rate': item.includes_mixed_tax_rate,
    }


def get_picture(event, picture, size=None):
    thumb = None
    if size:
        try:
            thumb = get_thumbnail(picture.name, size).thumb.url
        except:
            logger.exception(f'Failed to create thumbnail of {picture.name}')
    if not thumb:
        thumb = default_storage.url(picture.name)
    return urljoin(build_absolute_uri(event, 'presale:event.index'), thumb)


class WidgetAPIProductList(EventListMixin, View):

    def _get_items(self):
        qs = self.request.event.items
        if 'items' in self.request.GET:
            qs = qs.filter(pk__in=[pk.strip() for pk in self.request.GET.get('items').split(",") if pk.strip().isdigit()])
        if 'categories' in self.request.GET:
            qs = qs.filter(category__pk__in=[pk.strip() for pk in self.request.GET.get('categories').split(",") if pk.strip().isdigit()])
        variation_filter = None
        if 'variations' in self.request.GET:
            variation_filter = [int(pk.strip()) for pk in self.request.GET.get('variations').split(",") if pk.strip().isdigit()]
            qs = qs.filter(
                pk__in=ItemVariation.objects.filter(
                    item__event=self.request.event,
                    pk__in=variation_filter,
                ).values_list('item_id', flat=True)
            )

        items, display_add_to_cart = get_grouped_items(
            self.request.event,
            subevent=self.subevent,
            voucher=self.voucher,
            channel=self.request.sales_channel,
            base_qs=qs,
            require_seat=None,
            memberships=(
                self.request.customer.usable_memberships(
                    for_event=self.subevent or self.request.event,
                    testmode=self.request.event.testmode
                ) if getattr(self.request, 'customer', None) else None
            ),
        )

        grps = []
        for cat, g in item_group_by_category([i for i in items if not i.requires_seat]):
            grps.append({
                'id': cat.pk if cat else None,
                'name': str(cat.name) if cat else None,
                'description': str(rich_text(cat.description, safelinks=False)) if cat and cat.description else None,
                'items': [
                    {
                        'id': item.pk,
                        'name': str(item.name),
                        'picture': get_picture(self.request.event, item.picture, '60x60^') if item.picture else None,
                        'picture_fullsize': get_picture(self.request.event, item.picture) if item.picture else None,
                        'description': str(rich_text(item.description, safelinks=False)) if item.description else None,
                        'has_variations': item.has_variations,
                        'current_unavailability_reason': item.current_unavailability_reason,
                        'order_min': item.min_per_order,
                        'order_max': item.order_max if not item.has_variations else None,
                        'price': price_dict(item, item.display_price) if not item.has_variations else None,
                        'suggested_price': price_dict(item, item.suggested_price) if not item.has_variations else None,
                        'min_price': item.min_price if item.has_variations else None,
                        'max_price': item.max_price if item.has_variations else None,
                        'allow_waitinglist': item.allow_waitinglist,
                        'mandatory_priced_addons': item.mandatory_priced_addons,
                        'free_price': item.free_price,
                        'avail': [
                            item.cached_availability[0],
                            item.cached_availability[1] if item.do_show_quota_left else None
                        ] if not item.has_variations else None,
                        'original_price': (
                            (item.original_price.net
                             if self.request.event.settings.display_net_prices
                             else item.original_price.gross)
                            if item.original_price else None
                        ),
                        'variations': [
                            {
                                'id': var.id,
                                'value': str(var.value),
                                'order_max': var.order_max,
                                'description': str(rich_text(var.description, safelinks=False)) if var.description else None,
                                'price': price_dict(item, var.display_price),
                                'suggested_price': price_dict(item, var.suggested_price),
                                'original_price': (
                                    (
                                        var.original_price.net
                                        if self.request.event.settings.display_net_prices
                                        else var.original_price.gross
                                    ) if var.original_price else None
                                ) or (
                                    (
                                        item.original_price.net
                                        if self.request.event.settings.display_net_prices
                                        else item.original_price.gross
                                    ) if item.original_price else None
                                ),
                                'avail': [
                                    var.cached_availability[0],
                                    var.cached_availability[1] if item.do_show_quota_left else None
                                ],
                                'current_unavailability_reason': var.current_unavailability_reason,
                            } for var in item.available_variations if (not variation_filter or var.id in variation_filter)
                        ]

                    } for item in g
                ]
            })
        return grps, display_add_to_cart, len(items), items

    def post_process(self, data):
        data['poweredby'] = get_powered_by(self.request, safelink=False)

    def response(self, data):
        self.post_process(data)
        resp = JsonResponse(data)
        resp['Access-Control-Allow-Origin'] = '*'
        resp._csp_ignore = True
        return resp

    def get(self, request, *args, **kwargs):
        if not hasattr(request, 'event'):
            return self._get_event_list(request, **kwargs)

        if not request.event.live:
            return self.response({
                'error': gettext('This ticket shop is currently disabled.')
            })

        if not request.event.all_sales_channels and request.sales_channel.identifier not in (s.identifier for s in request.event.limit_sales_channels.all()):
            return self.response({
                'error': gettext('Tickets for this event cannot be purchased on this sales channel.')
            })

        self.subevent = None
        if request.event.has_subevents:
            if 'subevent' in kwargs:
                self.subevent = request.event.subevents.filter(pk=kwargs['subevent'], active=True).first()
                if not self.subevent:
                    return self.response({
                        'error': gettext('The selected date does not exist in this event series.')
                    })
            else:
                return self._get_event_list(request, **kwargs)
        else:
            if 'subevent' in kwargs:
                return self.response({
                    'error': gettext('This is not an event series.')
                })
        return self._get_event_view(request, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        o = getattr(request, 'event', request.organizer)
        if 'lang' in request.GET and request.GET.get('lang') in [lc for lc, ll in settings.LANGUAGES]:
            with language(request.GET.get('lang'), o.settings.region):
                return self.get(request, **kwargs)
        else:
            return self.get(request, **kwargs)

    def _get_availability(self, ev, event, tz=None):
        availability = {}
        if ev.presale_is_running and event.settings.event_list_availability:
            if ev.best_availability_state == Quota.AVAILABILITY_OK:
                if ev.best_availability_is_low:
                    availability['color'] = 'green'
                    availability['text'] = gettext('Few tickets left')
                    availability['reason'] = 'low'
                else:
                    availability['color'] = 'green'
                    if ev.has_paid_item:
                        availability['text'] = pgettext('available_event_in_list', 'Buy now')
                    else:
                        availability['text'] = gettext('Book now')
                    availability['reason'] = 'ok'
            elif ev.waiting_list_active and (ev.best_availability_state is not None and ev.best_availability_state >= 0):
                availability['color'] = 'orange'
                availability['text'] = gettext('Waiting list')
                availability['reason'] = 'waitinglist'
            elif ev.best_availability_state == Quota.AVAILABILITY_RESERVED:
                availability['color'] = 'red'
                availability['text'] = gettext('Reserved')
                availability['reason'] = 'reserved'
            elif ev.best_availability_state is not None and ev.best_availability_state < Quota.AVAILABILITY_RESERVED:
                availability['color'] = 'red'
                if ev.has_paid_item:
                    availability['text'] = gettext('Sold out')
                else:
                    availability['text'] = gettext('Fully booked')
                availability['reason'] = 'full'
            else:  # unknown / no product
                availability['color'] = 'none'
                availability['text'] = gettext('More info')
                availability['reason'] = 'unknown'
        elif ev.presale_is_running:
            availability['color'] = 'green'
            availability['text'] = gettext('Book now')
            availability['reason'] = 'ok'
        elif ev.presale_has_ended:
            availability['color'] = 'red'
            availability['text'] = gettext('Sale over')
            availability['reason'] = 'over'
        elif event.settings.presale_start_show_date and ev.presale_start:
            availability['color'] = 'orange'
            availability['text'] = gettext('from %(start_date)s') % {
                'start_date': date_format(ev.presale_start.astimezone(tz or event.timezone), "SHORT_DATE_FORMAT")
            }
            availability['reason'] = 'soon'
        else:
            availability['color'] = 'orange'
            availability['text'] = gettext('Soon')
            availability['reason'] = 'soon'
        return availability

    def _get_date_range(self, ev, event, tz=None):
        tz = tz or event.timezone
        dr = ev.get_date_range_display(tz)
        if event.settings.show_times:
            dr += " " + date_format(ev.date_from.astimezone(tz), "TIME_FORMAT")
            if event.settings.show_date_to and ev.date_to and ev.date_from.astimezone(tz).date() == ev.date_to.astimezone(tz).date():
                dr += " – " + date_format(ev.date_to.astimezone(tz), "TIME_FORMAT")
        return dr

    def _serialize_events(self, ebd):
        events = []
        for e in ebd:
            ev = e['event']
            if isinstance(ev, SubEvent):
                event = ev.event
            else:
                event = ev
            tz = ZoneInfo(e['timezone'])
            time = date_format(ev.date_from.astimezone(tz), 'TIME_FORMAT') if e.get('time') and event.settings.show_times else None
            if time and ev.date_to and ev.date_from.astimezone(tz).date() == ev.date_to.astimezone(tz).date() and event.settings.show_date_to:
                time += ' – ' + date_format(ev.date_to.astimezone(tz), 'TIME_FORMAT')
            events.append({
                'name': str(ev.name),
                'time': time,
                'continued': e['continued'],
                'location': str(ev.location),
                'date_range': self._get_date_range(ev, event, tz=tz),
                'availability': self._get_availability(ev, event, tz=tz),
                'event_url': build_absolute_uri(event, 'presale:event.index'),
                'subevent': ev.pk if isinstance(ev, SubEvent) else None,
            })
        return events

    def _get_event_list(self, request, **kwargs):
        data = {}
        o = getattr(request, 'event', request.organizer)
        list_type = self.request.GET.get("style", o.settings.event_list_type)
        data['list_type'] = list_type
        data['meta_filter_fields'] = [
            {**v, "key": k} for k, v in meta_filtersets(request.organizer, getattr(request, 'event', None)).items()
        ]

        if hasattr(self.request, 'event') and data['list_type'] not in ("calendar", "week"):
            # only allow list-view of more than 50 subevents if ordering is by data as this can be done in the database
            # ordering by name is currently not supported in database due to I18NField-JSON
            ordering = self.request.event.settings.get('frontpage_subevent_ordering', default='date_ascending', as_type=str)
            if ordering not in ("date_ascending", "date_descending") and self.request.event.subevents.filter(date_from__gt=now()).count() > 50:
                if self.request.event.settings.event_list_type not in ("calendar", "week"):
                    self.request.event.settings.event_list_type = "calendar"
                data['list_type'] = list_type = 'calendar'

        if hasattr(self.request, 'event'):
            data['name'] = str(request.event.name)
            data['frontpage_text'] = str(rich_text(request.event.settings.frontpage_text, safelinks=False))

        cache_key = ':'.join([
            'widget.py',
            'eventlist',
            request.organizer.slug,
            request.event.slug if hasattr(request, 'event') else '-',
            list_type,
            request.GET.urlencode(),
            get_language(),
        ])
        cached_data = cache.get(cache_key)
        if cached_data:
            return self.response(cached_data)

        if list_type == "calendar":
            self._set_month_year()
            _, ndays = calendar.monthrange(self.year, self.month)

            data['date'] = date(self.year, self.month, 1)
            if hasattr(self.request, 'event'):
                tz = self.request.event.timezone
            else:
                tz = self.request.organizer.timezone
            before = datetime(self.year, self.month, 1, 0, 0, 0, tzinfo=tz) - timedelta(days=1)
            after = datetime(self.year, self.month, ndays, 0, 0, 0, tzinfo=tz) + timedelta(days=1)
            if hasattr(self.request, 'event') and self.request.event.settings.event_calendar_future_only:
                limit_before = min(after, now().astimezone(tz))
            else:
                limit_before = before

            ebd = defaultdict(list)

            if hasattr(self.request, 'event'):
                add_subevents_for_days(
                    filter_qs_by_attr(
                        self.request.event.subevents_annotated(self.request.sales_channel).filter(
                            Q(event__all_sales_channels=True) |
                            Q(event__limit_sales_channels=self.request.sales_channel),
                        ), self.request
                    ),
                    limit_before, after, ebd, set(), self.request.event,
                    kwargs.get('cart_namespace')
                )
            else:
                timezones = set()
                add_events_for_days(
                    self.request,
                    filter_qs_by_attr(
                        Event.annotated(self.request.organizer.events, self.request.sales_channel).filter(
                            Q(all_sales_channels=True) | Q(limit_sales_channels=self.request.sales_channel),
                        ), self.request
                    ),
                    limit_before, after, ebd, timezones
                )
                add_subevents_for_days(filter_qs_by_attr(SubEvent.annotated(SubEvent.objects.filter(
                    Q(event__all_sales_channels=True) |
                    Q(event__limit_sales_channels__identifier=self.request.sales_channel.identifier),
                    event__organizer=self.request.organizer,
                    event__is_public=True,
                    event__live=True,
                ).prefetch_related(
                    'event___settings_objects', 'event__organizer___settings_objects'
                ), self.request.sales_channel), self.request), limit_before, after, ebd, timezones)

            data['weeks'] = weeks_for_template(ebd, self.year, self.month)
            for w in data['weeks']:
                for d in w:
                    if not d:
                        continue
                    d['events'] = self._serialize_events(d['events'] or [])
        elif list_type == "week":
            self._set_week_year()

            if hasattr(self.request, 'event'):
                tz = self.request.event.timezone
            else:
                tz = self.request.organizer.timezone

            week = isoweek.Week(self.year, self.week)
            data['week'] = [self.year, self.week]
            before = datetime(
                week.monday().year, week.monday().month, week.monday().day, 0, 0, 0, tzinfo=tz
            ) - timedelta(days=1)
            after = datetime(
                week.sunday().year, week.sunday().month, week.sunday().day, 0, 0, 0, tzinfo=tz
            ) + timedelta(days=1)

            if hasattr(self.request, 'event') and self.request.event.settings.event_calendar_future_only:
                limit_before = now().astimezone(tz)
            else:
                limit_before = before

            ebd = defaultdict(list)
            if hasattr(self.request, 'event'):
                add_subevents_for_days(
                    filter_qs_by_attr(self.request.event.subevents_annotated(self.request.sales_channel), self.request),
                    limit_before, after, ebd, set(), self.request.event,
                    kwargs.get('cart_namespace')
                )
            else:
                timezones = set()
                add_events_for_days(
                    self.request,
                    filter_qs_by_attr(Event.annotated(self.request.organizer.events, self.request.sales_channel), self.request),
                    limit_before, after, ebd, timezones
                )
                add_subevents_for_days(filter_qs_by_attr(SubEvent.annotated(SubEvent.objects.filter(
                    event__organizer=self.request.organizer,
                    event__is_public=True,
                    event__live=True,
                ).prefetch_related(
                    'event___settings_objects', 'event__organizer___settings_objects'
                ), self.request.sales_channel), self.request), limit_before, after, ebd, timezones)

            data['days'] = days_for_template(ebd, week)
            for d in data['days']:
                d['events'] = self._serialize_events(d['events'] or [])
        else:
            offset = int(self.request.GET.get("offset", 0))
            limit = 50
            if hasattr(self.request, 'event'):
                evs = filter_qs_by_attr(
                    self.request.event.subevents_annotated(self.request.sales_channel),
                    self.request,
                    match_subevents_with_conditions=(
                        Q(Q(date_to__isnull=True) & Q(date_from__gte=now() - timedelta(hours=24)))
                        | Q(date_to__gte=now() - timedelta(hours=24))
                    ),
                )
                evs = self.request.event.subevents_sorted(evs)
                ordering = self.request.event.settings.get('frontpage_subevent_ordering', default='date_ascending', as_type=str)
                data['has_more_events'] = False
                if ordering in ("date_ascending", "date_descending"):
                    # fetch one more result than needed to check if more events exist
                    evs = list(evs[offset:offset + limit + 1])
                    if len(evs) > limit:
                        data['has_more_events'] = True
                        evs = evs[:limit]

                tz = request.event.timezone
                if self.request.event.settings.event_list_available_only:
                    evs = [
                        se for se in evs
                        if not se.presale_has_ended and (
                            se.best_availability_state is not None and
                            se.best_availability_state >= Quota.AVAILABILITY_RESERVED
                        )
                    ]

                data['events'] = [
                    {
                        'name': str(ev.name),
                        'location': str(ev.location),
                        'date_range': self._get_date_range(ev, ev.event, tz),
                        'availability': self._get_availability(ev, ev.event, tz=tz),
                        'event_url': build_absolute_uri(ev.event, 'presale:event.index'),
                        'subevent': ev.pk,
                    } for ev in evs
                ]
            else:
                data['events'] = []
                qs = self._get_event_list_queryset()
                for event in qs:
                    tz = ZoneInfo(event.cache.get_or_set('timezone', lambda: event.settings.timezone))
                    if event.has_subevents:
                        dr = daterange(
                            event.min_from.astimezone(tz),
                            (event.max_fromto or event.max_to or event.max_from).astimezone(tz)
                        )
                        avail = {'color': 'none', 'text': gettext('Event series')}
                    else:
                        dr = self._get_date_range(event, event, tz)
                        avail = self._get_availability(event, event, tz=tz)
                    data['events'].append({
                        'name': str(event.name),
                        'location': str(event.location),
                        'date_range': dr,
                        'availability': avail,
                        'event_url': build_absolute_uri(event, 'presale:event.index'),
                    })

        cache.set(cache_key, data, 30)
        # These pages are cached for a really short duration – this should make them pretty accurate, while still
        # providing some protection against burst traffic.
        return self.response(data)

    def _get_event_view(self, request, **kwargs):
        cache_key = ':'.join([
            'widget.py',
            'event',
            request.organizer.slug,
            request.event.slug,
            str(self.subevent.pk) if self.subevent else "",
            request.GET.urlencode(),
            get_language(),
            request.sales_channel.identifier,
        ])
        if "cart_id" not in request.GET:
            cached_data = cache.get(cache_key)
            if cached_data:
                return self.response(cached_data)

        data = {
            'target_url': build_absolute_uri(request.event, 'presale:event.index'),
            'subevent': self.subevent.pk if self.subevent else None,
            'currency': request.event.currency,
            'display_net_prices': request.event.settings.display_net_prices,
            'use_native_spinners': request.event.settings.widget_use_native_spinners,
            'show_variations_expanded': request.event.settings.show_variations_expanded,
            'waiting_list_enabled': (self.subevent or request.event).waiting_list_active,
            'voucher_explanation_text': str(rich_text(request.event.settings.voucher_explanation_text, safelinks=False)),
            'error': None,
            'cart_exists': False
        }

        if 'cart_id' in request.GET and CartPosition.objects.filter(event=request.event, cart_id=request.GET.get('cart_id')).exists():
            data['cart_exists'] = True

        ev = self.subevent or request.event
        data['name'] = str(ev.name)

        templating_context = PlaceholderContext(event_or_subevent=ev, event=request.event)
        if self.subevent:
            data['frontpage_text'] = str(rich_text(templating_context.format(str(self.subevent.frontpage_text)), safelinks=False))
            data['location'] = str(rich_text(self.subevent.location, safelinks=False))
        else:
            data['frontpage_text'] = str(rich_text(templating_context.format(str(request.event.settings.frontpage_text)), safelinks=False))
            data['location'] = str(rich_text(request.event.location, safelinks=False))
        data['date_range'] = self._get_date_range(ev, request.event)
        fail = False

        vouchers_exist = self.request.event.get_cache().get('vouchers_exist')
        if vouchers_exist is None:
            vouchers_exist = self.request.event.vouchers.exists()
            self.request.event.get_cache().set('vouchers_exist', vouchers_exist)
        data['vouchers_exist'] = vouchers_exist

        if not ev.presale_is_running:
            data['vouchers_exist'] = False
            if ev.presale_has_ended:
                if request.event.settings.presale_has_ended_text:
                    data['error'] = str(request.event.settings.presale_has_ended_text)
                else:
                    data['error'] = gettext('The booking period for this event is over.')
            elif request.event.settings.presale_start_show_date:
                data['error'] = gettext('The booking period for this event will start on %(date)s at %(time)s.') % {
                    'date': date_format(ev.effective_presale_start.astimezone(request.event.timezone), "SHORT_DATE_FORMAT"),
                    'time': date_format(ev.effective_presale_start.astimezone(request.event.timezone), "TIME_FORMAT"),
                }
            else:
                data['error'] = gettext('The booking period for this event has not yet started.')

        self.voucher = None
        if 'voucher' in request.GET:
            try:
                self.voucher = request.event.vouchers.get(code__iexact=request.GET.get('voucher').strip())
                if self.voucher.redeemed >= self.voucher.max_usages:
                    data['error'] = error_messages['voucher_redeemed']
                    fail = True
                if self.voucher.valid_until is not None and self.voucher.valid_until < now():
                    data['error'] = error_messages['voucher_expired']
                    fail = True

                cart_id = get_or_create_cart_id(request, create=False)
                if cart_id:
                    redeemed_in_carts = CartPosition.objects.filter(
                        Q(voucher=self.voucher) & Q(event=request.event) &
                        (Q(expires__gte=now()) | Q(cart_id=get_or_create_cart_id(request)))
                    )
                else:
                    redeemed_in_carts = CartPosition.objects.filter(
                        Q(voucher=self.voucher) & Q(event=request.event) & Q(expires__gte=now())
                    )
                v_avail = self.voucher.max_usages - self.voucher.redeemed - redeemed_in_carts.count()

                if v_avail < 1:
                    data['error'] = error_messages['voucher_redeemed']
                    fail = True
            except Voucher.DoesNotExist:
                data['error'] = error_messages['voucher_invalid']
                fail = True

        if not fail and (ev.presale_is_running or request.event.settings.show_items_outside_presale_period):
            data['items_by_category'], data['display_add_to_cart'], data['itemnum'], items = self._get_items()
            data['display_add_to_cart'] = data['display_add_to_cart'] and ev.presale_is_running
        else:
            items = []
            data['items_by_category'] = []
            data['display_add_to_cart'] = False
            data['itemnum'] = 0
            data['vouchers_exist'] = False

        data['has_seating_plan'] = ev.seating_plan is not None
        data['has_seating_plan_waitinglist'] = False
        if ev.waiting_list_active and ev.presale_is_running:
            for i in items:
                if not i.allow_waitinglist or not i.requires_seat:
                    continue

                if i.has_variations:
                    for v in i.available_variations:
                        if v.cached_availability[0] != Quota.AVAILABILITY_OK:
                            data['has_seating_plan_waitinglist'] = True
                            break
                else:
                    if i.cached_availability[0] != Quota.AVAILABILITY_OK:
                        data['has_seating_plan_waitinglist'] = True
                        break

        if "cart_id" not in request.GET:
            cache.set(cache_key, data, 10)
            # These pages are cached for a really short duration – this should make them pretty accurate with
            # regards to availability display, while still providing some protection against burst traffic.
        return self.response(data)
