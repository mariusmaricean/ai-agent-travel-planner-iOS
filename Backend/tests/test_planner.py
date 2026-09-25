import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from unittest.mock import patch

from app.agents import (
    Critique,
    DestinationResearchAgent,
    ItineraryCriticAgent,
    TripCoordinatorAgent,
)
from app.history import TripPlanHistoryStore
from app.jobs import TripPlanJobRunner
from app.planner import create_trip_plan
from app.runs import INTERRUPTED_RUN_MESSAGE, TripPlanRunStore
from app.schemas import (
    DestinationResearch,
    MemoryNote,
    TripDay,
    TripOption,
    TripPlanRequest,
    TripPlanResponse,
)
from app.telemetry import capture_provider_telemetry, provider_event_title
from app.tools import (
    AmadeusFlightProvider,
    AmadeusFlightProviderConfig,
    DestinationResearchQuery,
    FareOption,
    FlightProviderError,
    FlightSearchQuery,
    ItineraryPlanningInput,
    ItineraryRevisionInput,
    LocationResolutionCache,
    OpenAIDestinationResearcher,
    OpenAIItineraryPlanner,
    OpenAIItineraryReviser,
    OpenAIPlannerConfig,
    OpenMeteoDestinationResearchProvider,
    OpenMeteoDestinationResearchProviderConfig,
    OpenMeteoLocation,
    PROVIDER_LOGGER_NAME,
    ResolvedLocation,
    TicketmasterEvent,
    TicketmasterEventsProvider,
    TicketmasterEventsProviderConfig,
    TravelPlanningToolRouter,
    amadeus_fare_options,
    amadeus_location_keyword,
    amadeus_resolved_location,
    cached_location,
    configured_destination_research_provider,
    configured_flight_provider,
    configured_location_resolver,
    iata_location_code,
    local_resolved_location,
    log_provider_event,
    location_resolution_cache,
    model_backed_destination_researcher,
    model_backed_itinerary_planner,
    open_meteo_location,
    open_meteo_weather_summary,
    rule_based_itinerary_reviser,
    ticketmaster_datetime,
    ticketmaster_events,
)


class TripPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        location_resolution_cache.clear()
        self.openai_api_key = os.environ.pop("OPENAI_API_KEY", None)
        self.amadeus_env = {
            key: os.environ.pop(key, None)
            for key in [
                "FLIGHT_PROVIDER",
                "AMADEUS_CLIENT_ID",
                "AMADEUS_CLIENT_SECRET",
                "AMADEUS_BASE_URL",
                "AMADEUS_TIMEOUT_SECONDS",
                "AMADEUS_CURRENCY_CODE",
                "AMADEUS_MAX_OFFERS",
                "AMADEUS_ADULTS",
                "LOCATION_CACHE_MAX_ENTRIES",
                "DESTINATION_RESEARCH_PROVIDER",
                "OPEN_METEO_GEOCODING_URL",
                "OPEN_METEO_FORECAST_URL",
                "OPEN_METEO_TIMEOUT_SECONDS",
                "TICKETMASTER_API_KEY",
                "TICKETMASTER_COUNTRY_CODE",
                "TICKETMASTER_EVENTS_URL",
                "TICKETMASTER_MAX_EVENTS",
                "TICKETMASTER_TIMEOUT_SECONDS",
                "TRIP_PLAN_HISTORY_LIMIT",
                "TRIP_PLAN_HISTORY_STORE_PATH",
                "TRIP_PLAN_RUN_STORE_PATH",
                "TRIP_PLAN_RUN_WORKERS",
            ]
        }

    def tearDown(self) -> None:
        location_resolution_cache.clear()
        if self.openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        for key, value in self.amadeus_env.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def test_create_trip_plan_returns_contract_shape(self) -> None:
        request = make_request()

        response = create_trip_plan(request)

        self.assertEqual(len(response.trips), 3)
        self.assertEqual(response.trips[0].route, "New York -> Lisbon")
        self.assertEqual(response.trips[0].days[0].label, "D1")
        self.assertIsNotNone(response.memory)
        self.assertEqual(response.memory[-1].title, "Last best option")

    def test_create_trip_plan_routes_provider_functions(self) -> None:
        calls: list[str] = []
        saved_memory = [MemoryNote(title="Preference", detail="Likes culture walks.")]
        request = make_request(rememberPreferences=False, memory=saved_memory)

        def destination_researcher(query: DestinationResearchQuery) -> DestinationResearch:
            calls.append("research")
            self.assertEqual(query.destination, "Lisbon")
            self.assertEqual(query.mood, "Culture")
            self.assertEqual(query.memory, saved_memory)

            return make_destination_research()

        def flight_provider(query: FlightSearchQuery) -> list[FareOption]:
            calls.append("flight")
            self.assertEqual(query.origin, "New York")
            self.assertEqual(query.destination, "Lisbon")
            self.assertEqual(query.budget, 1400)

            return [
                FareOption(
                    name="Provider Fare",
                    fare=510,
                    score=97,
                    meta="provider fare",
                )
            ]

        def itinerary_planner(planning_input: ItineraryPlanningInput) -> list[TripOption]:
            calls.append("itinerary")
            self.assertEqual(planning_input.constraints, "Window seat, no red-eye flights.")
            self.assertEqual(planning_input.memory, saved_memory)
            self.assertEqual(planning_input.fares[0].name, "Provider Fare")
            self.assertEqual(
                planning_input.destination_research,
                make_destination_research(),
            )

            return [
                TripOption(
                    name="Provider Plan",
                    route="New York -> Lisbon",
                    fare=planning_input.fares[0].fare,
                    score=planning_input.fares[0].score,
                    meta="model planned",
                    days=[
                        TripDay(
                            label="D1",
                            title="Provider day",
                            detail="Generated by the injected planner.",
                        )
                    ],
                )
            ]

        tools = TravelPlanningToolRouter(
            flight_provider=flight_provider,
            itinerary_planner=itinerary_planner,
            destination_researcher=destination_researcher,
        )

        response = create_trip_plan(request, tools=tools)

        self.assertEqual(calls, ["research", "flight", "itinerary"])
        self.assertEqual(response.trips[0].name, "Provider Plan")
        self.assertEqual(response.memory, saved_memory)

    def test_destination_research_agent_routes_research_tool(self) -> None:
        calls: list[str] = []

        def destination_researcher(query: DestinationResearchQuery) -> DestinationResearch:
            calls.append(query.destination)
            return make_destination_research()

        tools = TravelPlanningToolRouter(
            flight_provider=lambda query: [],
            itinerary_planner=lambda planning_input: [],
            destination_researcher=destination_researcher,
        )
        agent = DestinationResearchAgent(tools)

        research = agent.run(make_request())

        self.assertEqual(calls, ["Lisbon"])
        self.assertEqual(research.summary, "Lisbon culture research.")

    def test_coordinator_revises_rejected_trip_once(self) -> None:
        request = make_request()
        tools = TravelPlanningToolRouter(
            flight_provider=lambda query: [
                FareOption(
                    name="Over Budget",
                    fare=1500,
                    score=93,
                    meta="test fare",
                )
            ],
            itinerary_planner=lambda planning_input: [
                TripOption(
                    name="Over Budget",
                    route="New York -> Lisbon",
                    fare=1500,
                    score=93,
                    meta="test fare",
                    days=[
                        TripDay(
                            label="D1",
                            title="Packed day",
                            detail="Museum, market, tram, castle, dinner.",
                        )
                    ],
                )
            ],
        )
        coordinator = TripCoordinatorAgent(
            tools=tools,
            critic_agent=RejectingCriticAgent(),
        )

        response = coordinator.run(request)

        self.assertEqual(len(response.trips), 1)
        self.assertIn("critic-reviewed", response.trips[0].meta)
        self.assertIn("revision-needs-review", response.trips[0].meta)
        self.assertNotIn("Critic revision", response.trips[0].days[-1].detail)
        self.assertIn("Prioritize free sights", response.trips[0].days[-1].detail)

    def test_coordinator_emits_agent_progress_events(self) -> None:
        events: list[tuple[str, str, str]] = []
        request = make_request()
        tools = TravelPlanningToolRouter(
            flight_provider=lambda query: [
                FareOption(
                    name="Provider Fare",
                    fare=510,
                    score=97,
                    meta="provider fare",
                )
            ],
            itinerary_planner=lambda planning_input: [
                TripOption(
                    name="Provider Plan",
                    route="New York -> Lisbon",
                    fare=planning_input.fares[0].fare,
                    score=planning_input.fares[0].score,
                    meta="model planned",
                    days=[
                        TripDay(
                            label="D1",
                            title="Provider day",
                            detail="Generated by the injected planner.",
                        )
                    ],
                )
            ],
            destination_researcher=lambda query: make_destination_research(),
        )
        coordinator = TripCoordinatorAgent(
            tools=tools,
            progress=lambda step, status, title, detail: events.append((step, status, title)),
        )

        response = coordinator.run(request)

        self.assertEqual(len(response.trips), 1)
        self.assertEqual(
            events,
            [
                ("research", "active", "Research destination"),
                ("research", "done", "Research destination"),
                ("flights", "active", "Search flights"),
                ("flights", "done", "Search flights"),
                ("itinerary", "active", "Build itinerary"),
                ("itinerary", "done", "Build itinerary"),
                ("critic", "active", "Critic review"),
                ("critic", "done", "Critic review"),
                ("revision", "done", "Revise if needed"),
                ("memory", "active", "Finalize memory"),
                ("memory", "done", "Finalize memory"),
            ],
        )

    def test_run_store_tracks_events_and_result(self) -> None:
        store = TripPlanRunStore()
        created = store.create()
        result = TripPlanResponse(trips=[], memory=[])

        store.emit(
            run_id=created.runId,
            step="research",
            status="active",
            title="Research destination",
        )
        store.emit(
            run_id=created.runId,
            step="research",
            status="done",
            title="Research destination",
        )
        store.complete(created.runId, result)

        snapshot = store.snapshot(created.runId)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.status, "completed")
        self.assertEqual(snapshot.result, result)
        self.assertEqual([event.status for event in snapshot.events], ["active", "done"])

    def test_file_backed_run_store_restores_completed_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            store = TripPlanRunStore(path=path)
            created = store.create()
            result = TripPlanResponse(trips=[], memory=[])

            store.emit(
                run_id=created.runId,
                step="research",
                status="done",
                title="Research destination",
            )
            store.complete(created.runId, result)

            restored = TripPlanRunStore(path=path).snapshot(created.runId)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, "completed")
        self.assertEqual(restored.result, result)
        self.assertEqual(restored.events[0].step, "research")

    def test_file_backed_run_store_marks_running_snapshot_failed_after_restart(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            store = TripPlanRunStore(path=path)
            created = store.create()
            store.emit(
                run_id=created.runId,
                step="research",
                status="active",
                title="Research destination",
            )

            restored = TripPlanRunStore(path=path).snapshot(created.runId)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, "failed")
        self.assertEqual(restored.error, INTERRUPTED_RUN_MESSAGE)
        self.assertEqual(restored.events[-1].status, "failed")
        self.assertEqual(restored.events[-1].step, "research")

    def test_file_backed_history_store_restores_saved_plan_and_memory(self) -> None:
        request = make_request()
        response = TripPlanResponse(
            trips=[],
            memory=[MemoryNote(title="Preference", detail="Likes culture walks.")],
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            store = TripPlanHistoryStore(path=path)

            saved = store.save(request, response, run_id="run-1")
            restored_store = TripPlanHistoryStore(path=path)
            restored = restored_store.get(saved.id)
            latest_memory = restored_store.latest_memory()

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.runId, "run-1")
        self.assertEqual(restored.request.destination, "Lisbon")
        self.assertEqual(restored.response, response)
        self.assertEqual(latest_memory, response.memory)

    def test_history_store_limits_saved_records(self) -> None:
        request = make_request()
        response = TripPlanResponse(trips=[], memory=[])

        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            store = TripPlanHistoryStore(path=path, max_entries=1)

            first = store.save(request, response)
            second = store.save(request, response)
            restored_store = TripPlanHistoryStore(path=path, max_entries=1)

        self.assertIsNone(restored_store.get(first.id))
        self.assertEqual(restored_store.recent()[0].id, second.id)

    def test_history_store_scopes_records_and_memory_by_traveler(self) -> None:
        first_memory = [MemoryNote(title="Preference", detail="Likes culture walks.")]
        second_memory = [MemoryNote(title="Preference", detail="Needs quiet mornings.")]

        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            store = TripPlanHistoryStore(path=path)

            first = store.save(
                make_request(traveler_id="traveler-a"),
                TripPlanResponse(trips=[], memory=first_memory),
            )
            second = store.save(
                make_request(traveler_id="traveler-b"),
                TripPlanResponse(trips=[], memory=second_memory),
            )
            restored_store = TripPlanHistoryStore(path=path)

        first_history = restored_store.recent(traveler_id="traveler-a")
        second_history = restored_store.recent(traveler_id="traveler-b")

        self.assertEqual([record.id for record in first_history], [first.id])
        self.assertEqual([record.id for record in second_history], [second.id])
        self.assertEqual(first_history[0].travelerId, "traveler-a")
        self.assertEqual(first_history[0].request.travelerId, "traveler-a")
        self.assertIsNone(restored_store.get(second.id, traveler_id="traveler-a"))
        self.assertEqual(
            restored_store.latest_memory(traveler_id="traveler-a"),
            first_memory,
        )
        self.assertEqual(
            restored_store.latest_memory(traveler_id="traveler-b"),
            second_memory,
        )

    def test_provider_telemetry_handler_emits_run_events(self) -> None:
        store = TripPlanRunStore()
        created = store.create()

        with capture_provider_telemetry(created.runId, store):
            log_provider_event(
                "flight.mock_fallback",
                destination="LIS",
                origin="NYC",
                reason="missing_amadeus_credentials",
            )

        snapshot = store.snapshot(created.runId)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.events[0].step, "telemetry")
        self.assertEqual(snapshot.events[0].status, "done")
        self.assertEqual(snapshot.events[0].title, "Flight provider fallback")
        self.assertIn("reason: missing_amadeus_credentials", snapshot.events[0].detail)

    def test_trip_plan_job_runner_completes_run_snapshot(self) -> None:
        store = TripPlanRunStore()
        history_store = TripPlanHistoryStore()
        runner = TripPlanJobRunner(store=store, history_store=history_store, max_workers=1)
        created = store.create()

        try:
            result = runner.run(created.runId, make_request())
        finally:
            runner.shutdown()

        snapshot = store.snapshot(created.runId)

        self.assertIsNotNone(result)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.status, "completed")
        self.assertIsNotNone(snapshot.result)
        self.assertEqual(snapshot.events[0].step, "research")
        self.assertEqual(snapshot.events[-1].step, "memory")
        self.assertIn("telemetry", [event.step for event in snapshot.events])
        self.assertEqual(len(history_store.recent()), 1)
        self.assertEqual(history_store.recent()[0].runId, created.runId)

    def test_rule_based_revision_rewrites_overpacked_day(self) -> None:
        request = make_request()
        trip = TripOption(
            name="Packed Plan",
            route="New York -> Lisbon",
            fare=620,
            score=93,
            meta="test fare",
            days=[
                TripDay(
                    label="D1",
                    title="Too much",
                    detail="Museum, market, tram, castle, dinner.",
                )
            ],
        )

        revised_trip = rule_based_itinerary_reviser(
            ItineraryRevisionInput(
                request=request,
                original_trip=trip,
                critic_score=76,
                issues=["D1 may be too packed for a mobile travel plan."],
                recommendations=["Add a protected break or reduce the number of activities."],
            )
        )

        self.assertEqual(revised_trip.name, trip.name)
        self.assertEqual(revised_trip.fare, trip.fare)
        self.assertIn("critic-reviewed", revised_trip.meta)
        self.assertEqual(
            revised_trip.days[0].detail,
            "Museum, market, then a protected break before dinner. "
            "Constraints honored: Window seat, no red-eye flights.",
        )

    def test_model_backed_planner_falls_back_without_api_key(self) -> None:
        planning_input = make_planning_input()

        trips = model_backed_itinerary_planner(planning_input)

        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0].name, "Provider Fare")
        self.assertEqual(trips[0].route, "New York -> Lisbon")

    def test_model_backed_researcher_falls_back_without_api_key(self) -> None:
        research = model_backed_destination_researcher(make_destination_research_query())

        self.assertEqual(research.destination, "Lisbon")
        self.assertIn("Lisbon", research.summary)
        self.assertEqual(len(research.highlights), 3)

    def test_open_meteo_location_parses_geocoding_response(self) -> None:
        location = open_meteo_location(
            {
                "results": [
                    {
                        "name": "Lisbon",
                        "country": "Portugal",
                        "latitude": 38.7167,
                        "longitude": -9.1333,
                        "timezone": "Europe/Lisbon",
                    }
                ]
            },
            "Lisbon",
        )

        self.assertEqual(
            location,
            OpenMeteoLocation(
                query="Lisbon",
                name="Lisbon",
                country="Portugal",
                latitude=38.7167,
                longitude=-9.1333,
                timezone="Europe/Lisbon",
            ),
        )

    def test_open_meteo_weather_summary_parses_daily_forecast(self) -> None:
        location = OpenMeteoLocation(
            query="Lisbon",
            name="Lisbon",
            country="Portugal",
            latitude=38.7167,
            longitude=-9.1333,
            timezone="Europe/Lisbon",
        )

        summary = open_meteo_weather_summary(
            {
                "daily": {
                    "temperature_2m_max": [24.5, 27.0],
                    "temperature_2m_min": [15.0, 17.0],
                    "precipitation_probability_max": [20, 55],
                    "weather_code": [2, 61],
                }
            },
            location,
            forecast_days=2,
        )

        self.assertEqual(summary.location, location)
        self.assertEqual(summary.min_temperature_c, 15.0)
        self.assertEqual(summary.max_temperature_c, 27.0)
        self.assertEqual(summary.precipitation_probability_max, 55)
        self.assertEqual(summary.weather_code, 2)

    def test_open_meteo_provider_returns_weather_research(self) -> None:
        provider = OpenMeteoDestinationResearchProvider(
            OpenMeteoDestinationResearchProviderConfig(
                geocoding_url="https://geocoding.test/search",
                forecast_url="https://forecast.test/v1",
                timeout_seconds=3,
            )
        )

        with patch(
            "app.tools.json_response",
            side_effect=[
                {
                    "results": [
                        {
                            "name": "Lisbon",
                            "country": "Portugal",
                            "latitude": 38.7167,
                            "longitude": -9.1333,
                            "timezone": "Europe/Lisbon",
                        }
                    ]
                },
                {
                    "daily": {
                        "temperature_2m_max": [24.5, 27.0],
                        "temperature_2m_min": [15.0, 17.0],
                        "precipitation_probability_max": [20, 55],
                        "weather_code": [2, 61],
                    }
                },
            ],
        ):
            with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
                research = provider.research(make_destination_research_query())

        self.assertEqual(research.destination, "Lisbon")
        self.assertIn("Open-Meteo", research.summary)
        self.assertIn("15-27 C", research.summary)
        self.assertIn("Build indoor alternates", research.cautions[-1])
        self.assertLogContains(logs, '"event": "research.open_meteo_geocode"')
        self.assertLogContains(logs, '"event": "research.open_meteo_forecast"')

    def test_ticketmaster_events_parse_event_response(self) -> None:
        events = ticketmaster_events(ticketmaster_events_payload())

        self.assertEqual(
            events,
            [
                TicketmasterEvent(
                    name="Lisbon Summer Sessions",
                    venue="Campo Pequeno",
                    city="Lisbon",
                    local_start="2026-07-12 20:30:00",
                    classification="Music / Rock",
                    url="https://ticketmaster.test/event",
                )
            ],
        )

    def test_ticketmaster_provider_returns_event_research(self) -> None:
        provider = TicketmasterEventsProvider(
            TicketmasterEventsProviderConfig(
                api_key="test-key",
                events_url="https://ticketmaster.test/events.json",
                timeout_seconds=3,
            )
        )

        with patch("app.tools.json_response", return_value=ticketmaster_events_payload()):
            with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
                research = provider.research(make_destination_research_query())

        self.assertEqual(research.destination, "Lisbon")
        self.assertIn("Ticketmaster", research.summary)
        self.assertIn("Lisbon Summer Sessions", research.highlights[0])
        self.assertIn("Confirm event availability", research.cautions[-2])
        self.assertLogContains(logs, '"event": "research.ticketmaster_events"')
        self.assertLogContains(logs, '"event_count": 1')

    def test_configured_destination_research_provider_uses_ticketmaster(self) -> None:
        os.environ["DESTINATION_RESEARCH_PROVIDER"] = "ticketmaster"
        os.environ["TICKETMASTER_API_KEY"] = "test-key"

        with patch(
            "app.tools.TicketmasterEventsProvider.research",
            return_value=make_destination_research(),
        ) as research:
            result = configured_destination_research_provider(make_destination_research_query())

        self.assertEqual(result, make_destination_research())
        self.assertEqual(research.call_count, 1)

    def test_configured_ticketmaster_provider_falls_back_without_api_key(self) -> None:
        os.environ["DESTINATION_RESEARCH_PROVIDER"] = "ticketmaster"

        with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
            result = configured_destination_research_provider(make_destination_research_query())

        self.assertIsNone(result)
        self.assertLogContains(logs, '"provider": "ticketmaster"')
        self.assertLogContains(logs, '"error": "missing_ticketmaster_api_key"')

    def test_ticketmaster_datetime_uses_utc_z_suffix(self) -> None:
        value = datetime(2026, 7, 11, 9, 15, 22, 123, tzinfo=timezone.utc)

        self.assertEqual(ticketmaster_datetime(value), "2026-07-11T09:15:22Z")

    def test_provider_telemetry_title_includes_ticketmaster_events(self) -> None:
        self.assertEqual(
            provider_event_title({"event": "research.ticketmaster_events"}),
            "Event provider results",
        )

    def test_configured_destination_research_provider_uses_open_meteo(self) -> None:
        os.environ["DESTINATION_RESEARCH_PROVIDER"] = "open_meteo"

        with patch(
            "app.tools.OpenMeteoDestinationResearchProvider.research",
            return_value=make_destination_research(),
        ) as research:
            result = configured_destination_research_provider(make_destination_research_query())

        self.assertEqual(result, make_destination_research())
        self.assertEqual(research.call_count, 1)

    def test_model_backed_researcher_returns_provider_research_without_api_key(self) -> None:
        os.environ["DESTINATION_RESEARCH_PROVIDER"] = "open_meteo"

        with patch(
            "app.tools.OpenMeteoDestinationResearchProvider.research",
            return_value=make_destination_research(),
        ):
            research = model_backed_destination_researcher(make_destination_research_query())

        self.assertEqual(research, make_destination_research())

    def test_configured_flight_provider_falls_back_without_amadeus_credentials(self) -> None:
        with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
            fares = configured_flight_provider(
                FlightSearchQuery(
                    origin="New York",
                    destination="Lisbon",
                    depart_date=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
                    return_date=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
                    budget=1400,
                )
            )

        self.assertEqual(len(fares), 3)
        self.assertIn("source: mock", fares[0].meta)
        self.assertLogContains(logs, '"event": "flight.mock_fallback"')
        self.assertLogContains(logs, '"reason": "missing_amadeus_credentials"')

    def test_configured_flight_provider_logs_provider_failure(self) -> None:
        class FailingProvider:
            def search(self, query: FlightSearchQuery) -> list[FareOption]:
                raise FlightProviderError("Amadeus unavailable")

        with patch("app.tools.AmadeusFlightProvider.from_environment", return_value=FailingProvider()):
            with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
                fares = configured_flight_provider(
                    FlightSearchQuery(
                        origin="CPH",
                        destination="CLJ",
                        depart_date=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
                        return_date=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
                        budget=600,
                    )
                )

        self.assertEqual(len(fares), 3)
        self.assertLogContains(logs, '"event": "flight.provider_failure"')
        self.assertLogContains(logs, '"event": "flight.mock_fallback"')

    def test_iata_location_code_normalizes_common_city_names(self) -> None:
        self.assertEqual(iata_location_code("Copenhaga"), "CPH")
        self.assertEqual(iata_location_code("Cluj-Napoca"), "CLJ")
        self.assertEqual(iata_location_code("LIS"), "LIS")
        self.assertIsNone(iata_location_code("Unknown Place"))

    def test_local_location_resolver_returns_alias_metadata(self) -> None:
        with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
            location = local_resolved_location("Copenhaga")

        self.assertEqual(
            location,
            ResolvedLocation(
                query="Copenhaga",
                code="CPH",
                name="Copenhaga",
                source="local alias",
            ),
        )
        self.assertLogContains(logs, '"event": "location.local_alias"')
        self.assertLogContains(logs, '"code": "CPH"')

    def test_configured_location_resolver_uses_local_alias_without_credentials(self) -> None:
        location = configured_location_resolver("Cluj-Napoca")

        self.assertIsNotNone(location)
        assert location is not None
        self.assertEqual(location.code, "CLJ")
        self.assertEqual(location.source, "local alias")

    def test_cached_location_uses_normalized_cache_key(self) -> None:
        cache = LocationResolutionCache()
        calls: list[str] = []

        def resolver(value: str) -> Optional[ResolvedLocation]:
            calls.append(value)
            return ResolvedLocation(
                query=value,
                code="CPH",
                name="Copenhagen",
                source="test",
            )

        first = cached_location("Copenhaga", cache, resolver)
        with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
            second = cached_location("copenhaga", cache, resolver)

        self.assertEqual(first, second)
        self.assertEqual(calls, ["Copenhaga"])
        self.assertLogContains(logs, '"event": "location.cache_hit"')

    def test_location_cache_evicts_oldest_entry(self) -> None:
        cache = LocationResolutionCache(max_entries=1)
        paris = ResolvedLocation(
            query="Paris",
            code="PAR",
            name="Paris",
            source="test",
        )
        lisbon = ResolvedLocation(
            query="Lisbon",
            code="LIS",
            name="Lisbon",
            source="test",
        )

        cache.set("Paris", paris)
        cache.set("Lisbon", lisbon)

        self.assertIsNone(cache.get("Paris"))
        self.assertEqual(cache.get("Lisbon"), lisbon)

    def test_tool_router_resolves_locations_before_flight_search(self) -> None:
        observed_queries: list[FlightSearchQuery] = []
        request = TripPlanRequest(
            origin="Copenhaga",
            destination="Cluj-Napoca",
            departDate=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
            returnDate=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
            budget=600,
            constraints="Window seat, no red-eye flights.",
            rememberPreferences=True,
            mood="Culture",
            memory=[],
        )

        def location_resolver(value: str) -> Optional[ResolvedLocation]:
            codes = {
                "Copenhaga": "CPH",
                "Cluj-Napoca": "CLJ",
            }
            code = codes.get(value)
            if code is None:
                return None

            return ResolvedLocation(
                query=value,
                code=code,
                name=value,
                source="test",
            )

        tools = TravelPlanningToolRouter(
            flight_provider=lambda query: observed_queries.append(query) or [],
            itinerary_planner=lambda planning_input: [],
            location_resolver=location_resolver,
        )

        tools.search_flights(request)

        self.assertEqual(observed_queries[0].origin, "CPH")
        self.assertEqual(observed_queries[0].destination, "CLJ")

    def test_amadeus_location_keyword_uses_first_significant_word(self) -> None:
        self.assertEqual(amadeus_location_keyword("San Francisco"), "SAN")
        self.assertEqual(amadeus_location_keyword("Cluj-Napoca"), "CLUJ")
        self.assertEqual(amadeus_location_keyword("Copenhaga"), "COPENHAGA")
        self.assertIsNone(amadeus_location_keyword("A"))

    def test_amadeus_resolved_location_parse_location_response(self) -> None:
        location = amadeus_resolved_location(
            {
                "data": [
                    {
                        "name": "COPENHAGEN",
                        "iataCode": "cph",
                        "subType": "CITY",
                    }
                ]
            },
            "Copenhaga",
        )

        self.assertEqual(
            location,
            ResolvedLocation(
                query="Copenhaga",
                code="CPH",
                name="COPENHAGEN",
                source="Amadeus Location Search",
            ),
        )

    def test_amadeus_resolved_location_rejects_malformed_payload(self) -> None:
        with self.assertRaises(FlightProviderError):
            amadeus_resolved_location({"data": {}}, "Copenhaga")

    def test_amadeus_remote_location_lookup_logs_hit(self) -> None:
        provider = AmadeusFlightProvider(
            AmadeusFlightProviderConfig(client_id="client", client_secret="secret")
        )

        with patch(
            "app.tools.json_response",
            return_value={
                "data": [
                    {
                        "name": "COPENHAGEN",
                        "iataCode": "CPH",
                    }
                ]
            },
        ):
            with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
                location = provider.remote_resolved_location("Copenhaga", "token")

        self.assertIsNotNone(location)
        assert location is not None
        self.assertEqual(location.code, "CPH")
        self.assertLogContains(logs, '"event": "location.amadeus_lookup"')
        self.assertLogContains(logs, '"result": "hit"')

    def test_amadeus_search_logs_flight_offers(self) -> None:
        provider = AmadeusFlightProvider(
            AmadeusFlightProviderConfig(client_id="client", client_secret="secret")
        )
        query = FlightSearchQuery(
            origin="CPH",
            destination="CLJ",
            depart_date=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
            return_date=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
            budget=600,
        )

        with patch.object(AmadeusFlightProvider, "access_token", return_value="token"):
            with patch.object(
                AmadeusFlightProvider,
                "flight_offers",
                return_value={
                    "data": [
                        {
                            "price": {"grandTotal": "423.50"},
                            "itineraries": [{"segments": [{"carrierCode": "SK"}]}],
                        }
                    ]
                },
            ):
                with self.assertLogs(PROVIDER_LOGGER_NAME, level="INFO") as logs:
                    fares = provider.search(query)

        self.assertEqual(len(fares), 1)
        self.assertLogContains(logs, '"event": "flight.amadeus_offers"')
        self.assertLogContains(logs, '"offer_count": 1')

    def test_amadeus_config_reads_environment(self) -> None:
        os.environ["AMADEUS_CLIENT_ID"] = "client"
        os.environ["AMADEUS_CLIENT_SECRET"] = "secret"
        os.environ["AMADEUS_BASE_URL"] = "https://example.test"
        os.environ["AMADEUS_TIMEOUT_SECONDS"] = "7"
        os.environ["AMADEUS_CURRENCY_CODE"] = "EUR"
        os.environ["AMADEUS_MAX_OFFERS"] = "2"
        os.environ["AMADEUS_ADULTS"] = "3"

        config = AmadeusFlightProviderConfig.from_environment()

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.client_id, "client")
        self.assertEqual(config.client_secret, "secret")
        self.assertEqual(config.base_url, "https://example.test")
        self.assertEqual(config.timeout_seconds, 7)
        self.assertEqual(config.currency_code, "EUR")
        self.assertEqual(config.max_offers, 2)
        self.assertEqual(config.adults, 3)

    def test_amadeus_fare_options_parse_offer_response(self) -> None:
        fares = amadeus_fare_options(
            {
                "data": [
                    {
                        "price": {"grandTotal": "423.50"},
                        "itineraries": [
                            {
                                "segments": [
                                    {"carrierCode": "SK"},
                                    {"carrierCode": "LH"},
                                ]
                            },
                            {
                                "segments": [
                                    {"carrierCode": "LH"},
                                ]
                            },
                        ],
                    }
                ]
            },
            "USD",
        )

        self.assertEqual(len(fares), 1)
        self.assertEqual(fares[0].name, "Amadeus Offer 1")
        self.assertEqual(fares[0].fare, 423.50)
        self.assertEqual(fares[0].score, 92)
        self.assertIn("source: Amadeus", fares[0].meta)
        self.assertIn("SK/LH", fares[0].meta)
        self.assertIn("1 connection", fares[0].meta)

    def test_amadeus_fare_options_reject_malformed_payload(self) -> None:
        with self.assertRaises(FlightProviderError):
            amadeus_fare_options({"data": {}}, "USD")

    def test_openai_planner_request_body_uses_structured_outputs(self) -> None:
        planner = OpenAIItineraryPlanner(OpenAIPlannerConfig(api_key="test-key"))

        body = planner.request_body(make_planning_input())
        prompt_payload = json_from_body(body)

        self.assertEqual(body["model"], "gpt-5.5")
        self.assertEqual(body["reasoning"]["effort"], "low")
        self.assertFalse(body["store"])
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertEqual(body["text"]["format"]["name"], "travel_itinerary_options")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(prompt_payload["destinationResearch"]["destination"], "Lisbon")

    def test_openai_destination_research_request_body_uses_structured_outputs(self) -> None:
        researcher = OpenAIDestinationResearcher(OpenAIPlannerConfig(api_key="test-key"))

        body = researcher.request_body(make_destination_research_query())
        prompt_payload = json_from_body(body)

        self.assertEqual(body["model"], "gpt-5.5")
        self.assertEqual(body["reasoning"]["effort"], "low")
        self.assertFalse(body["store"])
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertEqual(body["text"]["format"]["name"], "destination_research")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(prompt_payload["trip"]["destination"], "Lisbon")
        self.assertEqual(prompt_payload["providerResearch"]["destination"], "")
        self.assertIn("Prefer experience types", prompt_payload["successCriteria"][1])

    def test_openai_destination_research_prompt_includes_provider_research(self) -> None:
        researcher = OpenAIDestinationResearcher(OpenAIPlannerConfig(api_key="test-key"))
        query = make_destination_research_query()

        body = researcher.request_body(
            DestinationResearchQuery(
                origin=query.origin,
                destination=query.destination,
                depart_date=query.depart_date,
                return_date=query.return_date,
                budget=query.budget,
                mood=query.mood,
                constraints=query.constraints,
                memory=query.memory,
                provider_research=make_destination_research(),
            )
        )
        prompt_payload = json_from_body(body)

        self.assertEqual(prompt_payload["providerResearch"]["summary"], "Lisbon culture research.")
        self.assertEqual(prompt_payload["providerResearch"]["highlights"][0], "Tile museum")

    def test_openai_revision_request_body_uses_critique_context(self) -> None:
        reviser = OpenAIItineraryReviser(OpenAIPlannerConfig(api_key="test-key"))

        body = reviser.request_body(
            ItineraryRevisionInput(
                request=make_request(),
                original_trip=TripOption(
                    name="Packed Plan",
                    route="New York -> Lisbon",
                    fare=620,
                    score=93,
                    meta="test fare",
                    days=[
                        TripDay(
                            label="D1",
                            title="Too much",
                            detail="Museum, market, tram, castle, dinner.",
                        )
                    ],
                ),
                critic_score=76,
                issues=["D1 may be too packed for a mobile travel plan."],
                recommendations=["Add a protected break or reduce the number of activities."],
                destination_research=make_destination_research(),
            )
        )
        prompt_payload = json_from_body(body)

        self.assertEqual(body["text"]["format"]["name"], "travel_itinerary_revision")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(prompt_payload["originalTrip"]["name"], "Packed Plan")
        self.assertEqual(prompt_payload["critique"]["score"], 76)
        self.assertEqual(prompt_payload["destinationResearch"]["summary"], "Lisbon culture research.")
        self.assertIn("Return exactly one revised option", prompt_payload["successCriteria"][0])

    def assertLogContains(self, logs, value: str) -> None:
        self.assertIn(value, "\n".join(logs.output))


class RejectingCriticAgent(ItineraryCriticAgent):
    def run(
        self,
        request: TripPlanRequest,
        trip: TripOption,
    ) -> Critique:
        return Critique(
            approved=False,
            score=72,
            issues=["Trip is over budget."],
            recommendations=["Add a budget-safe revision note."],
        )


def make_request(
    rememberPreferences: bool = True,
    memory: Optional[list[MemoryNote]] = None,
    traveler_id: str | None = None,
) -> TripPlanRequest:
    return TripPlanRequest(
        travelerId=traveler_id,
        origin="New York",
        destination="Lisbon",
        departDate=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
        returnDate=datetime(2026, 7, 16, 9, tzinfo=timezone.utc),
        budget=1400,
        constraints="Window seat, no red-eye flights.",
        rememberPreferences=rememberPreferences,
        mood="Culture",
        memory=memory or [],
    )


def make_planning_input() -> ItineraryPlanningInput:
    request = make_request(memory=[MemoryNote(title="Preference", detail="Likes culture walks.")])

    return ItineraryPlanningInput(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.departDate,
        return_date=request.returnDate,
        budget=request.budget,
        duration=5,
        mood=request.mood,
        constraints=request.constraints,
        memory=request.memory,
        fares=[
            FareOption(
                name="Provider Fare",
                fare=510,
                score=97,
                meta="provider fare",
            )
        ],
        destination_research=make_destination_research(),
    )


def make_destination_research() -> DestinationResearch:
    return DestinationResearch(
        destination="Lisbon",
        summary="Lisbon culture research.",
        highlights=[
            "Tile museum",
            "Old town walk",
            "Riverfront concert",
        ],
        cautions=[
            "Avoid stacking too many cross-town activities into one day.",
        ],
        local_tips=[
            "Hold one open block for local recommendations.",
        ],
    )


def make_destination_research_query() -> DestinationResearchQuery:
    request = make_request(memory=[MemoryNote(title="Preference", detail="Likes culture walks.")])

    return DestinationResearchQuery(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.departDate,
        return_date=request.returnDate,
        budget=request.budget,
        mood=request.mood,
        constraints=request.constraints,
        memory=request.memory,
    )


def ticketmaster_events_payload() -> dict:
    return {
        "_embedded": {
            "events": [
                {
                    "name": "Lisbon Summer Sessions",
                    "url": "https://ticketmaster.test/event",
                    "dates": {
                        "start": {
                            "localDate": "2026-07-12",
                            "localTime": "20:30:00",
                        }
                    },
                    "classifications": [
                        {
                            "segment": {"name": "Music"},
                            "genre": {"name": "Rock"},
                            "subGenre": {"name": "Undefined"},
                        }
                    ],
                    "_embedded": {
                        "venues": [
                            {
                                "name": "Campo Pequeno",
                                "city": {"name": "Lisbon"},
                            }
                        ]
                    },
                }
            ]
        }
    }


def json_from_body(body: dict) -> dict:
    return json.loads(body["input"][1]["content"])


if __name__ == "__main__":
    unittest.main()
