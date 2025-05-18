# Siku Fan integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

**This component will set up the following platforms.**

| Platform | Description |
| -------- | ----------- |
| `fan`    | Siku Fan    |

Integration for https://www.siku.at/produkte/ wifi fans

### Tested on

- "Siku RV 50 W Pro WIFI v1"

The fan is sold under different brands, for instance :

- [SIKU RV](https://www.siku.at/produkte/)
- [Blauberg Group](https://blauberg-group.com)
- [Blauberg Ventilatoren](https://blaubergventilatoren.de/en/catalog/single-room-reversible-units-vento/functions/2899)
- [VENTS Twinfresh](https://ventilation-system.com/catalog/decentralized-hru-for-residential-use/)
  - Breezy fans use a new protocol and is incompatible with this integration
- [DUKA One](https://dukaventilation.dk/produkter/1-rums-ventilationsloesninger)
- [Oxxify](https://raumluft-shop.de/lueftung/dezentrale-lueftungsanlage-mit-waermerueckgewinnung/oxxify.html)
- [Twinfresh](https://foris.no/produktkategori/miniventilasjon/miniventilasjon-miniventilasjon/)

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hmn&repository=siku-integration&category=integration)

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `siku`.
4. Download _all_ the files from the `custom_components/siku/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Siku Fan integration"

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/siku/translations/en.json
custom_components/siku/__init__.py
custom_components/siku/api.py
custom_components/siku/config_flow.py
custom_components/siku/const.py
custom_components/siku/cordinator.py
custom_components/siku/fan.py
custom_components/siku/manifest.json
custom_components/siku/strings.json
```

## Configuration is done in the UI

<!---->

## Report issues

If you have any issues with this integration, please [open an issue](https://github.com/hmn/siku-integration/issues).

Make sure to include debug logs. See https://www.home-assistant.io/integrations/logger/ for more information on how to enable debug logs.

```
logger:
  default: info
  logs:
    custom_components.siku: debug
```

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/hnicolaisen
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/hmn/siku-integration.svg?style=for-the-badge
[commits]: https://github.com/hmn/siku-integration/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/hmn/siku-integration.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40hmn-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/hmn/siku-integration.svg?style=for-the-badge
[releases]: https://github.com/hmn/siku-integration/releases
[user_profile]: https://github.com/hmn
