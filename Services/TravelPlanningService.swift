import Foundation

protocol TravelPlanningServicing: Sendable {
    func makeTrips(for brief: TripBrief) async -> [TripOption]
}

struct MockTravelPlanningService: TravelPlanningServicing, Sendable {
    func makeTrips(for brief: TripBrief) async -> [TripOption] {
        let route = "\(brief.origin) -> \(brief.destination)"
        let baseFare = max(320, (brief.budget * 0.42).rounded())
        let focus = brief.mood.focusItems

        return [
            TripOption(
                name: "Balanced Sprint",
                route: route,
                fare: baseFare + 70,
                score: 94,
                meta: "\(brief.duration) days | morning outbound | 1 checked bag",
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
                meta: "\(brief.duration) days | one connection | budget winner",
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
                meta: "\(brief.duration) days | direct flight | aisle-friendly timing",
                days: [
                    TripDay(label: "D1", title: "Direct arrival", detail: "Midday landing, easy transfer, no late-night commitments."),
                    TripDay(label: "D2", title: "Prime slot", detail: "\(focus[1]) anchored by the highest-fit booking window."),
                    TripDay(label: "D3", title: "Buffer day", detail: "\(focus[2]) with an airport transfer already staged.")
                ]
            )
        ]
    }
}
