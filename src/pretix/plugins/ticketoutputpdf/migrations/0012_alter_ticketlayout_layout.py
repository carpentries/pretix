# Generated by Django 4.2.17 on 2024-12-29 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ticketoutputpdf', '0011_sales_channels_remove_old_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketlayout',
            name='layout',
            field=models.TextField(default='[\n    {\n        "type": "barcodearea",\n        "page": 1,\n        "left": "130.40",\n        "bottom": "204.50",\n        "size": "64.00",\n        "content": "secret",\n        "text": "",\n        "text_i18n": {},\n        "nowhitespace": false,\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ]\n    },\n    {\n        "type": "poweredby",\n        "page": 1,\n        "left": "88.72",\n        "bottom": "10.00",\n        "size": "20.00",\n        "content": "dark"\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "272.09",\n        "fontsize": "14.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "177.07",\n        "height": "11.80",\n        "content": "event_name",\n        "text": "Sample event name",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "261.77",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "113.03",\n        "height": "7.83",\n        "content": "itemvar",\n        "text": "Sample product – sample variation",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "251.30",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "113.03",\n        "height": "7.83",\n        "content": "attendee_name",\n        "text": "Dr John Doe",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "240.30",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "113.03",\n        "height": "7.83",\n        "content": "event_begin",\n        "text": "2017-05-31 20:00",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "231.30",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "113.03",\n        "height": "7.83",\n        "content": "seat",\n        "text": "Ground floor, Row 3, Seat 4",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.35",\n        "bottom": "203.43",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "113.03",\n        "height": "25.70",\n        "content": "event_location",\n        "text": "Random City",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "bottom",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "101.50",\n        "bottom": "193.33",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "91.93",\n        "height": "7.83",\n        "content": "secret",\n        "text": "tdmruoekvkpbv1o2mv8xccvqcikvr58u",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "51.50",\n        "bottom": "193.33",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "47.38",\n        "height": "7.83",\n        "content": "price",\n        "text": "123.45 EUR",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "right",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    },\n    {\n        "type": "textcontainer",\n        "page": 1,\n        "locale": "",\n        "left": "16.50",\n        "bottom": "193.33",\n        "fontsize": "13.0",\n        "lineheight": "1",\n        "color": [\n            0,\n            0,\n            0,\n            1\n        ],\n        "fontfamily": "Open Sans",\n        "bold": false,\n        "italic": false,\n        "width": "32.32",\n        "height": "7.83",\n        "content": "order",\n        "text": "A1B2C",\n        "text_i18n": {},\n        "rotation": 0,\n        "align": "left",\n        "verticalalign": "middle",\n        "autoresize": true,\n        "splitlongwords": true\n    }\n]'),
        ),
    ]
