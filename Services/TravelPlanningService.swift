import Foundation

typealias TravelPlanningProgressHandler = @MainActor @Sendable (AgentRunProgressEvent) -> Void

protocol TravelPlanningServicing: Sendable {
    func makePlan(
        for brief: TripBrief,
        progress: TravelPlanningProgressHandler?
    ) async throws -> TripPlanResult
}

extension TravelPlanningServicing {
    func makePlan(for brief: TripBrief) async throws -> TripPlanResult {
        try await makePlan(for: brief, progress: nil)
    }
}

struct MockTravelPlanningService: TravelPlanningServicing, Sendable {
    func makePlan(
        for brief: TripBrief,
        progress: TravelPlanningProgressHandler?
    ) async throws -> TripPlanResult {
        try await emitMockProgress(for: brief, progress: progress)

        let route = "\(brief.origin) -> \(brief.destination)"
        let baseFare = max(320, (brief.budget * 0.42).rounded())
        let focus = brief.mood.focusItems

        let trips = [
            TripOption(
                name: "Balanced Sprint",
                route: route,
                fare: baseFare + 70,
                score: 94,
                meta: "\(brief.duration) days | morning outbound | 1 checked bag | source: local mock",
                days: [
                    TripDay(label: "D1", title: "Arrive light", detail: "\(focus[0]) after check-in, early dinner near the hotel."),
                    TripDay(label: "D2", title: "Deep day", detail: "\(focus[1]) with a protected two-hour open block."),
                    TripDay(label: "D3", title: "Easy close", detail: "\(focus[2]) before a late afternoon return.")
                ]
            ),
            TripOption(
                name: "Lowest Fare",
                route: route,
                fare: baseFare - 45,
                score: 88,
                meta: "\(brief.duration) days | one connection | budget winner | source: local mock",
                days: [
                    TripDay(label: "D1", title: "Fly lean", detail: "Carry-on timing with a low-risk connection window."),
                    TripDay(label: "D2", title: "Local layer", detail: "\(focus[0]) plus a neighborhood dinner reservation."),
                    TripDay(label: "D3", title: "Flexible finish", detail: "Open morning held for weather or saved recommendations.")
                ]
            ),
            TripOption(
                name: "Comfort Pick",
                route: route,
                fare: baseFare + 180,
                score: 91,
                meta: "\(brief.duration) days | direct flight | aisle-friendly timing | source: local mock",
                days: [
                    TripDay(label: "D1", title: "Direct arrival", detail: "Midday landing, easy transfer, no late-night commitments."),
                    TripDay(label: "D2", title: "Prime slot", detail: "\(focus[1]) anchored by the highest-fit booking window."),
                    TripDay(label: "D3", title: "Buffer day", detail: "\(focus[2]) with an airport transfer already staged.")
                ]
            )
        ]

        return TripPlanResult(trips: trips, memory: nil)
    }

    private func emitMockProgress(
        for brief: TripBrief,
        progress: TravelPlanningProgressHandler?
    ) async throws {
        let events = [
            AgentRunProgressEvent(
                step: .research,
                status: .active,
                title: "Research destination",
                detail: "Studying \(brief.destination) for \(brief.mood.rawValue.lowercased()) goals."
            ),
            AgentRunProgressEvent(
                step: .research,
                status: .done,
                title: "Research destination",
                detail: "\(brief.destination) context ready."
            ),
            AgentRunProgressEvent(
                step: .flights,
                status: .active,
                title: "Search flights",
                detail: "Checking \(brief.origin) to \(brief.destination) fare options."
            ),
            AgentRunProgressEvent(
                step: .flights,
                status: .done,
                title: "Search flights",
                detail: "Found 3 fare options."
            ),
            AgentRunProgressEvent(
                step: .itinerary,
                status: .active,
                title: "Build itinerary",
                detail: "Turning fare options into mobile trip cards."
            ),
            AgentRunProgressEvent(
                step: .itinerary,
                status: .done,
                title: "Build itinerary",
                detail: "Built 3 itinerary options."
            ),
            AgentRunProgressEvent(
                step: .critic,
                status: .active,
                title: "Critic review",
                detail: "Checking budget, constraints, and pacing."
            ),
            AgentRunProgressEvent(
                step: .critic,
                status: .done,
                title: "Critic review",
                detail: "Reviewed 3 trip options."
            ),
            AgentRunProgressEvent(
                step: .revision,
                status: .done,
                title: "Revise if needed",
                detail: "No revision needed."
            ),
            AgentRunProgressEvent(
                step: .memory,
                status: .active,
                title: "Finalize memory",
                detail: "Preparing local traveler memory updates."
            ),
            AgentRunProgressEvent(
                step: .memory,
                status: .done,
                title: "Finalize memory",
                detail: "Memory update ready."
            )
        ]

        for event in events {
            await progress?(event)
            try await Task.sleep(for: .milliseconds(180))
        }
    }
}
