from __future__ import annotations

import os

import requests
from loguru import logger


class JustWatchClient:
    BASE_URL = "https://apis.justwatch.com/graphql"
    DEFAULT_HEADERS = {
        "authority": "apis.justwatch.com",
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.justwatch.com",
        "accept-language": "en-US",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36 OPR/38.0.2220.41",
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

    ADD_TO_SEENLIST_MUTATION = """
    mutation SetInSeenlist($input: SetInSeenlistInput!, $country: Country!, $language: Language!, $includeUnreleasedEpisodes: Boolean!, $watchNowFilter: WatchNowOfferFilter!, $platform: Platform! = WEB) {
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
        self.auth_token = os.getenv("JUSTWATCH_AUTH_TOKEN")
        if not self.auth_token:
            logger.error("JUSTWATCH_AUTH_TOKEN environment variable not set.")
            msg = "Authorization token not found. Please set JUSTWATCH_AUTH_TOKEN."
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
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            logger.error(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None
        except ValueError as e:  # For JSON decoding errors
            logger.error(f"Failed to decode JSON response: {e}")
            logger.error(f"Response content: {response.content if 'response' in locals() else 'No response object'}")
            return None

    def get_title_id(self, title_name: str, title_type: str, release_year: int | str | None = None) -> str | None:
        logger.info(f"Searching for {title_type} '{title_name}' (Year: {release_year or 'Any'})...")

        search_filter = {
            "objectTypes": [title_type.upper()],
            "excludeIrrelevantTitles": False,
            "includeTitlesWithoutUrl": True,
            "searchQuery": title_name,
        }
        if release_year:
            try:
                search_filter["releaseYear"] = {"min": int(release_year), "max": int(release_year)}
            except ValueError:
                logger.warning(
                    f"Invalid release year '{release_year}' for '{title_name}'. Searching without year constraint."
                )

        variables = {
            "searchTitlesSortBy": "POPULAR",
            "searchTitlesFilter": search_filter,
            "language": self.language.split("-")[0],  # API expects 'en', not 'en-US' for language in some contexts
            "country": self.country,
        }

        response_data = self._make_request(self.SEARCH_QUERY_TEMPLATE, variables)

        if response_data and response_data.get("data", {}).get("popularTitles", {}).get("edges"):
            edges = response_data["data"]["popularTitles"]["edges"]
            if edges:
                # Add more sophisticated matching here if needed (e.g. year, exact title match)
                # For now, taking the first result
                node = edges[0]["node"]
                found_id = node["id"]
                found_title = node["content"]["title"]
                found_year = node["content"].get("originalReleaseYear", "N/A")
                found_type = node.get("objectType", "N/A")
                logger.success(f"Found: '{found_title}' ({found_type}, {found_year}) with ID: {found_id}")
                return found_id
            logger.warning(f"No results found for '{title_name}' ({title_type}, {release_year}).")
            return None
        logger.error(f"Could not retrieve ID for '{title_name}'. Response: {response_data}")
        return None

    def add_to_watchlist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to watchlist...")
        variables = {"input": {"id": justwatch_id, "state": True}}
        response_data = self._make_request(self.ADD_TO_WATCHLIST_MUTATION, variables)
        if response_data and response_data.get("data", {}).get("setInWatchlistV2", {}).get("title"):
            logger.success(f"Successfully added ID '{justwatch_id}' to watchlist.")
            return True
        logger.error(f"Failed to add ID '{justwatch_id}' to watchlist. Response: {response_data}")
        return False

    def add_to_seenlist(self, justwatch_id: str) -> bool:
        logger.info(f"Adding ID '{justwatch_id}' to seenlist...")
        # These variables are specific to the seenlist mutation and might need adjustment
        # based on precise API requirements or user preferences.
        # The original script had a very complex query and variables.
        # Simplifying here, but this might need revisiting if the API call fails.
        variables = {
            "platform": "WEB",
            "input": {
                "id": justwatch_id,
                "state": True,
                "country": self.country,  # Assuming this is required by the mutation
            },
            "country": self.country,
            "language": self.language,  # Seenlist query used full language e.g. en-US
            "watchNowFilter": {},  # Empty filter as per original
            "includeUnreleasedEpisodes": False,  # Default from original
        }
        response_data = self._make_request(self.ADD_TO_SEENLIST_MUTATION, variables)
        # The success check needs to be adapted based on the actual structure of a successful seenlist response
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
