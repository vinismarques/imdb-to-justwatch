from __future__ import annotations

import os
import re
from collections.abc import Sequence
from difflib import SequenceMatcher

import requests
from loguru import logger


class AuthenticationError(Exception):
    """The JustWatch token was rejected. Every later request would fail the same way."""


# Below this similarity a candidate is a different film, not a spelling variant of the one we asked for.
TITLE_MATCH_THRESHOLD = 0.85

YEAR_TOLERANCE = 1

# Widened window for the second attempt. Dropping the year constraint entirely matched
# 'The Wave' (2008) to an unrelated 2015 film, so the retry stays anchored to the year.
FALLBACK_YEAR_TOLERANCE = 3


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def title_distance(query: str, candidate: str) -> float:
    """0.0 for an exact match after normalization, approaching 1.0 as titles diverge."""
    return 1.0 - SequenceMatcher(None, normalize_title(query), normalize_title(candidate)).ratio()


def titles_match(query: str, candidate: str) -> bool:
    return title_distance(query, candidate) <= 1.0 - TITLE_MATCH_THRESHOLD


def best_alias_distance(aliases: Sequence[str], candidate: str) -> float:
    """Distance to whichever alias fits the candidate best.

    JustWatch answers with one name per title, and which one varies: the English title for
    'WALL-E', the original for 'Shingeki no Kyojin', the full canonical for 'Borat: Cultural
    Learnings...'. IMDb ships both names per row, so a title is a match when either one fits.
    """
    return min(title_distance(alias, candidate) for alias in aliases)


class JustWatchClient:
    BASE_URL = "https://apis.justwatch.com/graphql"
    DEFAULT_HEADERS = {
        "authority": "apis.justwatch.com",
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.justwatch.com",
        "accept-language": "en-US",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/51.0.2704.106 Safari/537.36 OPR/38.0.2220.41"
        ),
    }

    SEARCH_QUERY_TEMPLATE = """
    query GetSearchTitles(
        $country: Country!
        $language: Language!
        $searchTitlesFilter: TitleFilter
        $searchTitlesSortBy: PopularTitlesSorting! = POPULAR
    ) {
        popularTitles(
            first: 1
            country: $country
            filter: $searchTitlesFilter
            sortBy: $searchTitlesSortBy
        ) {
            edges {
                node {
                    id
                    objectType
                    content(country: $country, language: $language) {
                        title
                        originalReleaseYear
                    }
                }
            }
        }
    }
    """

    ADD_TO_WATCHLIST_MUTATION = """
    mutation SetInWatchlist($input: SetInTitleListInput!) {
        setInWatchlistV2(input: $input) {
            title {
                id
            }
        }
    }
    """

    ADD_TO_LIKELIST_MUTATION = """
    mutation SetInLikelist($input: SetInTitleListInput!) {
      setInLikelist(input: $input) {
        title {
          id
          likelistEntry {
            createdAt
            __typename
          }
          dislikelistEntry {
            createdAt
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """

    ADD_TO_DISLIKELIST_MUTATION = """
    mutation SetInDislikelist($input: SetInTitleListInput!) {
      setInDislikelist(input: $input) {
        title {
          id
          dislikelistEntry {
            createdAt
            __typename
          }
          likelistEntry {
            createdAt
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """

    ADD_TO_SEENLIST_MUTATION = """
    mutation SetInSeenlist(
      $input: SetInSeenlistInput!
      $country: Country!
      $language: Language!
      $includeUnreleasedEpisodes: Boolean!
      $watchNowFilter: WatchNowOfferFilter!
      $platform: Platform! = WEB
    ) {
      setInSeenlist(input: $input) {
        title {
          id
          ... on Movie {
            seenlistEntry {
              createdAt
              __typename
            }
            watchlistEntryV2 {
              createdAt
              __typename
            }
            __typename
          }
          ... on Show {
            seenState(country: $country) {
              progress
              caughtUp
              __typename
            }
            seasons {
              id
              seenState(country: $country) {
                progress
                __typename
              }
              episodes {
                id
                seenlistEntry {
                  createdAt
                  __typename
                }
                __typename
              }
              __typename
            }
            __typename
          }
          ... on Season {
            show {
              id
              seenState(country: $country) {
                progress
                caughtUp
                __typename
              }
              __typename
            }
            episodes {
              id
              seenlistEntry {
                createdAt
                __typename
              }
              __typename
            }
            seenState(country: $country) {
              progress
              caughtUp
              __typename
            }
            __typename
          }
          ... on Episode {
            seenlistEntry {
              createdAt
              __typename
            }
            show {
              id
              objectId
              objectType
              seenState(country: $country) {
                progress
                caughtUp
                __typename
              }
              watchNextEpisode(
                country: $country
                includeUnreleasedEpisodes: $includeUnreleasedEpisodes
              ) {
                id
                objectId
                objectType
                offerCount(country: $country, platform: $platform)
                season {
                  id
                  content(country: $country, language: $language) {
                    fullPath
                    __typename
                  }
                  seenState(country: $country) {
                    releasedEpisodeCount
                    seenEpisodeCount
                    progress
                    __typename
                  }
                  __typename
                }
                season {
                  id
                  content(country: $country, language: $language) {
                    posterUrl
                    __typename
                  }
                  __typename
                }
                content(country: $country, language: $language) {
                  title
                  episodeNumber
                  seasonNumber
                  upcomingReleases(releaseTypes: [DIGITAL]) @include(if: $includeUnreleasedEpisodes) {
                    releaseDate
                    label
                    __typename
                  }
                  __typename
                }
                watchNowOffer(country: $country, platform: $platform, filter: $watchNowFilter) {
                  ...WatchNowOffer
                  __typename
                }
                __typename
              }
              __typename
            }
            season {
              id
              seenState(country: $country) {
                progress
                caughtUp
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
    }

    fragment WatchNowOffer on Offer {
      __typename
      id
      standardWebURL
      preAffiliatedStandardWebURL
      streamUrl
      package {
        id
        icon
        packageId
        clearName
        shortName
        technicalName
        iconWide(profile: S160)
        hasRectangularIcon(country: $country, platform: WEB)
        __typename
      }
      retailPrice(language: $language)
      retailPriceValue
      lastChangeRetailPriceValue
      currency
      presentationType
      monetizationType
      availableTo
      dateCreated
      newElementCount
    }
    """

    def __init__(self, country: str = "US", language: str = "en-US") -> None:
        self.country = country
        self.language = language
        # Shells differ on quoting: Windows CMD keeps the quotes in the value, so strip them here.
        self.auth_token = os.getenv("JUSTWATCH_AUTH_TOKEN", "").strip().strip("\"'").strip()
        if not self.auth_token:
            logger.error("JUSTWATCH_AUTH_TOKEN environment variable not set.")
            msg = "Authorization token not found. Please set JUSTWATCH_AUTH_TOKEN."
            raise ValueError(msg)

        # Validate token encoding (common error: truncated token with '…' ellipsis)
        if not self.auth_token.isascii():
            logger.error(
                "JUSTWATCH_AUTH_TOKEN contains non-ASCII characters. Did you copy a truncated token ending in '…'?"
            )
            msg = "JUSTWATCH_AUTH_TOKEN must be ASCII. Check for truncated characters."
            raise ValueError(msg)

        if not self.auth_token.startswith("Bearer "):
            self.auth_token = f"Bearer {self.auth_token}"
        self.headers = {**self.DEFAULT_HEADERS, "Authorization": self.auth_token}
        # Referer can be dynamic based on operation, or a sensible default
        self.headers["referer"] = f"https://www.justwatch.com/{country.lower()}/watchlist"

    def _make_request(self, query: str, variables: dict) -> dict | None:
        payload = {"query": query, "variables": variables}
        try:
            response = requests.post(self.BASE_URL, headers=self.headers, json=payload)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            return response.json()
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            logger.error(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in (401, 403):
                logger.error(f"JustWatch rejected the token ({status}). Copy a fresh one and try again.")
                logger.error(f"Response content: {e.response.content if e.response is not None else 'None'}")
                msg = f"JustWatch rejected JUSTWATCH_AUTH_TOKEN ({status})."
                raise AuthenticationError(msg) from e
            logger.error(f"API request failed: {e}")
            logger.error(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            logger.error(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None
        except ValueError as e:
            logger.error(f"Value error during request (possibly encoding or invalid data): {e}")
            return None

    def _search_for_title(
        self,
        title_name: str,
        title_type: str,
        year: int | None,
        aliases: Sequence[str],
        tolerance: int = YEAR_TOLERANCE,
    ) -> str | None:
        """Returns the ID of the first result matching any alias, or None."""
        search_filter = {
            "objectTypes": [title_type.upper()],
            "excludeIrrelevantTitles": False,
            "includeTitlesWithoutUrl": True,
            "searchQuery": title_name,
        }
        if year is not None:
            # JustWatch and IMDb disagree by a year on titles with staggered releases.
            search_filter["releaseYear"] = {"min": year - tolerance, "max": year + tolerance}

        variables = {
            "searchTitlesSortBy": "POPULAR",
            "searchTitlesFilter": search_filter,
            "language": self.language.split("-")[0],  # API expects 'en', not 'en-US' for language in some contexts
            "country": self.country,
        }
        response_data = self._make_request(self.SEARCH_QUERY_TEMPLATE, variables)
        if response_data is None:
            logger.error(f"Could not retrieve ID for '{title_name}'. Response: {response_data}")
            return None

        candidates = []
        for edge in response_data.get("data", {}).get("popularTitles", {}).get("edges", []):
            node = edge["node"]
            found_title = node["content"]["title"]
            found_year = node["content"].get("originalReleaseYear", "N/A")
            if best_alias_distance(aliases, found_title) > 1.0 - TITLE_MATCH_THRESHOLD:
                logger.debug(f"Ignoring '{found_title}' ({found_year}): does not match any of {list(aliases)}.")
                continue
            candidates.append(node)

        if not candidates:
            return None

        # Results arrive by popularity, which ranks a similarly-named film above the one we asked for.
        best = min(candidates, key=lambda node: best_alias_distance(aliases, node["content"]["title"]))
        logger.success(
            f"Found: '{best['content']['title']}' ({best.get('objectType', 'N/A')}, "
            f"{best['content'].get('originalReleaseYear', 'N/A')}) with ID: {best['id']}"
        )
        return best["id"]

    def get_title_id(
        self,
        title_name: str,
        title_type: str,
        release_year: int | str | None = None,
        original_title: str | None = None,
    ) -> str | None:
        logger.info(f"Searching for {title_type} '{title_name}' (Year: {release_year or 'Any'})...")

        aliases = [title_name]
        if original_title and normalize_title(original_title) != normalize_title(title_name):
            aliases.append(original_title)
            logger.debug(f"Also accepting the original title '{original_title}' for '{title_name}'.")

        year: int | None = None
        if release_year:
            try:
                year = int(release_year)
            except ValueError:
                logger.warning(
                    f"Invalid release year '{release_year}' for '{title_name}'. Searching without year constraint."
                )

        found_id = self._search_for_title(title_name, title_type, year, aliases)
        if found_id is None and year is not None:
            logger.info(
                f"No match within {YEAR_TOLERANCE}y of {year} for '{title_name}'. "
                f"Widening to {FALLBACK_YEAR_TOLERANCE}y."
            )
            found_id = self._search_for_title(title_name, title_type, year, aliases, FALLBACK_YEAR_TOLERANCE)
        if found_id is None and len(aliases) > 1:
            logger.info(f"Retrying the search under the original title '{original_title}'.")
            found_id = self._search_for_title(aliases[1], title_type, year, aliases, FALLBACK_YEAR_TOLERANCE)
        if found_id is None:
            logger.warning(f"No result for '{title_name}' ({title_type}, {release_year}) had a matching title.")
        return found_id

    def add_to_watchlist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to watchlist...")
        variables = {"input": {"id": justwatch_id, "state": True}}
        response_data = self._make_request(self.ADD_TO_WATCHLIST_MUTATION, variables)
        if response_data and response_data.get("data", {}).get("setInWatchlistV2", {}).get("title"):
            logger.success(f"Successfully added ID '{justwatch_id}' to watchlist.")
            return True
        logger.error(f"Failed to add ID '{justwatch_id}' to watchlist. Response: {response_data}")
        return False

    def add_to_likelist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to likelist...")
        variables = {"input": {"id": justwatch_id, "state": True}}
        response_data = self._make_request(self.ADD_TO_LIKELIST_MUTATION, variables)
        if response_data and response_data.get("data", {}).get("setInLikelist", {}).get("title"):
            logger.success(f"Successfully added ID '{justwatch_id}' to likelist.")
            return True
        logger.error(f"Failed to add ID '{justwatch_id}' to likelist. Response: {response_data}")
        return False

    def add_to_dislikelist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to dislikelist...")
        variables = {"input": {"id": justwatch_id, "state": True}}
        response_data = self._make_request(self.ADD_TO_DISLIKELIST_MUTATION, variables)
        if response_data and response_data.get("data", {}).get("setInDislikelist", {}).get("title"):
            logger.success(f"Successfully added ID '{justwatch_id}' to dislikelist.")
            return True
        logger.error(f"Failed to add ID '{justwatch_id}' to dislikelist. Response: {response_data}")
        return False

    def add_to_seenlist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to seenlist...")
        variables = {
            "platform": "WEB",
            "input": {
                "id": justwatch_id,
                "state": True,
                "country": self.country,
            },
            "country": self.country,
            "language": self.language,
            "watchNowFilter": {},
            "includeUnreleasedEpisodes": False,
        }
        response_data = self._make_request(self.ADD_TO_SEENLIST_MUTATION, variables)
        if response_data and response_data.get("data", {}).get("setInSeenlist", {}).get("title"):
            logger.success(f"Successfully added ID '{justwatch_id}' to seenlist.")
            return True
        logger.error(f"Failed to add ID '{justwatch_id}' to seenlist. Response: {response_data}")
        return False


if __name__ == "__main__":
    # Example Usage (requires JUSTWATCH_AUTH_TOKEN to be set)
    # logger.add("app.log") # Optionally log to a file

    # print("Attempting to initialize JustWatchClient. Ensure JUSTWATCH_AUTH_TOKEN is set.")
    # try:
    #     client = JustWatchClient(country="US", language="en-US") # Or use your preferred country/language

    #     # Test search
    #     # title_id = client.get_title_id("The Matrix", "MOVIE", 1999)
    #     # if title_id:
    #     #     print(f"Found title ID: {title_id}")

    #     #     # Test add to watchlist (be cautious with real additions)
    #     #     # if client.add_to_watchlist(title_id):
    #     #     #     print(f"Added '{title_id}' to watchlist.")
    #     #     # else:
    #     #     #     print(f"Failed to add '{title_id}' to watchlist.")

    #     #     # Test add to seenlist (be cautious with real additions)
    #     #     # if client.add_to_seenlist(title_id):
    #     #     #      print(f"Added '{title_id}' to seenlist.")
    #     #     # else:
    #     #     #      print(f"Failed to add '{title_id}' to seenlist.")
    #     # else:
    #     #     print("Could not find title ID for 'The Matrix'.")

    #     # Example: Search for a show
    #     # show_id = client.get_title_id("Breaking Bad", "SHOW", 2008)
    #     # if show_id:
    #     #     print(f"Found show ID: {show_id}")
    #     # else:
    #     #     print("Could not find show ID for 'Breaking Bad'.")

    # except ValueError as e:
    #     print(f"Error: {e}")
    # except Exception as e:
    #     print(f"An unexpected error occurred: {e}")
    pass  # Keep the example usage commented out
