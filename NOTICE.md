# Attribution

群间世界 / Dynamics World integrates and adapts the following locally deployed sources:

- astrbot_plugin_worldbook v1.5.0, ysyhly, https://github.com/ysyhlly/astrbot_plugin_worldbook (role cards, lore matching, editor and import).
- astrbot_plugin_dynamic_life_state v0.4.11, Hola-Gracias, https://github.com/Hola-Gracias/astrbot_plugin_dynamic_life_state (schedule and persistent narrative engine), AGPL-3.0; full license retained in LICENSE.

The integrated work is distributed under AGPL-3.0. Original attributions are retained; integration does not claim original authorship of those modules. Source modifications include internal service composition, owned storage, lifecycle guards, unified UI, migration and capability discovery. The snapshot of worldbook supplied by its owner contains no LICENSE file; this notice does not assert a separate upstream license grant.

## Map components

- Azgaar Fantasy Map Generator 1.156.0, commit 67d555b83f0b2f40ae50b03c9bbfd018175acc6d, MIT. Original license at vendor/azgaar/LICENSE. Built without source modifications using the upstream electron renderer mode (which removes web analytics tags); only the browser renderer is bundled, not Electron.
- Leaflet 1.9.4, BSD-2-Clause, license at pages/world/vendor/leaflet/LICENSE.
- Bundled Azgaar runtime dependency notices are retained under vendor/licenses. Pinned provenance and build command are recorded in vendor/VERSIONS.json.
- Map generation uses the public window.FMG console surface in a fresh, local-only browser. Map state and character movement remain owned by Dynamics World.

Since v0.12.0 the large upstream texture files are excluded from the base distribution. Their unchanged version, URLs, sizes and SHA-256 digests are listed in texture-manifest.json; users may explicitly download them to their data directory. Azgaar's MIT notice remains included. Generic operation does not download franchise art; the optional Manosaba preset contains a short factual starter and source links, not official image binaries or a deployment owner's character data.

## Optional online geography and weather

- OpenStreetMap data: © OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright . Browser tiles: https://tile.openstreetmap.org/ subject to https://operations.osmfoundation.org/policies/tiles/ . Attribution is displayed in the map; tiles are not bundled.
- Open-Meteo weather API: https://open-meteo.com/ , weather data under CC BY 4.0; attribution displayed in the weather card. Forecast API: https://open-meteo.com/en/docs . Free API service is for non-commercial usage; commercial customer API keys are not implemented in this version.
- Open-Meteo geocoding uses GeoNames data; https://open-meteo.com/en/docs/geocoding-api . Search results are used only after explicit selection.

## Additional weather sources in v0.4

- MET Norway Locationforecast 2.0: https://api.met.no/weatherapi/locationforecast/2.0/documentation . Weather data © Norwegian Meteorological Institute, CC BY 4.0. Retain attribution and respect https://api.met.no/doc/TermsOfService . UI converts wind units and selects forecast periods without modifying provider values.
- QWeather: https://dev.qweather.com/ . The deployment owner's credentials and account terms govern requests. UI links https://developer.qweather.com/attribution.html . This implementation does not bundle QWeather data or credentials.
- Astral 3.2 (Apache-2.0), installed dependency for local sun position calculations: https://github.com/sffjunkie/astral . PyJWT with cryptography signs QWeather JWTs on the server.
