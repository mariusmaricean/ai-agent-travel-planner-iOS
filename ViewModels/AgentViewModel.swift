import Foundation
import SwiftUI

@MainActor
final class AgentViewModel: ObservableObject {
    @Published var origin = "New York"
    @Published var destination = "Lisbon"
    @Published var departDate = Calendar.current.date(byAdding: .day, value: 22, to: Date()) ?? Date()
    @Published var returnDate = Calendar.current.date(byAdding: .day, value: 27, to: Date()) ?? Date()
    @Published var budget = 1_400.0
    @Published var constraints = "Window seat, no red-eye flights, one free evening, save anything that beats the budget."
    @Published var rememberPreferences = true
    @Published var mood: TripMood = .culture
    @Published private(set) var runState: AgentRunState = .idle
    @Published var steps: [RunStep] = []
    @Published var trips: [TripOption] = []
    @Published var savedTrips: [TripOption] = []
    @Published var memory: [MemoryNote] = []
    @Published var activeTripID: UUID?

    private let planningService: TravelPlanningServicing
    private let stateStore: AgentStateStoring

    init(
        planningService: TravelPlanningServicing = TravelPlanningServiceFactory.makeService(),
        stateStore: AgentStateStoring = UserDefaultsAgentStateStore()
    ) {
        self.planningService = planningService
        self.stateStore = stateStore
        load()
        steps = makeSteps()
    }

    var savedCount: Int {
        savedTrips.count
    }

    var visibleTrips: [TripOption] {
        trips.isEmpty ? savedTrips : trips
    }

    var runStatus: String {
        runState.title
    }

    var isRunning: Bool {
        runState.isRunning
    }

    var errorMessage: String? {
        runState.errorMessage
    }

    var currentBrief: TripBrief {
        TripBrief(
            origin: origin,
            destination: destination,
            departDate: departDate,
            returnDate: returnDate,
            budget: budget,
            constraints: constraints,
            rememberPreferences: rememberPreferences,
            mood: mood,
            memory: memory
        )
    }

    func runAgent() async {
        guard !isRunning else { return }

        runState = .running
        trips = []
        steps = makeSteps()

        for index in steps.indices {
            steps[index].status = .active
            try? await Task.sleep(nanoseconds: 520_000_000)
            steps[index].status = .done
        }

        do {
            let result = try await planningService.makePlan(for: currentBrief)
            trips = result.trips
            activeTripID = result.trips.first?.id
            applyMemory(from: result)
            runState = .done
            save()
        } catch {
            runState = .failed(error.localizedDescription)
        }
    }

    private func applyMemory(from result: TripPlanResult) {
        if let serviceMemory = result.memory {
            memory = serviceMemory
            return
        }

        if let bestTrip = result.trips.first {
            updateMemory(bestTrip: bestTrip)
        }
    }

    func saveTrip(_ trip: TripOption) {
        if !savedTrips.contains(where: { $0.id == trip.id }) {
            savedTrips.insert(trip, at: 0)
        }
        activeTripID = trip.id
        save()
    }

    func saveBestTrip() {
        guard let bestTrip = trips.first ?? savedTrips.first else { return }
        saveTrip(bestTrip)
    }

    func selectTrip(_ trip: TripOption) {
        activeTripID = trip.id
        save()
    }

    func loadSample() {
        let samples: [(String, String, Double, TripMood, String)] = [
            (
                "New York",
                "Lisbon",
                1_400,
                .culture,
                "Window seat, no red-eye flights, one free evening, save anything that beats the budget."
            ),
            (
                "Chicago",
                "Tokyo",
                2_400,
                .food,
                "Direct flights preferred, quiet hotels, ramen day, one museum morning, avoid tight connections."
            ),
            (
                "Austin",
                "Mexico City",
                1_100,
                .recharge,
                "Carry-on only, early check-in, local markets, relaxed pace, save the lowest fare."
            )
        ]

        guard let sample = samples.randomElement() else { return }
        origin = sample.0
        destination = sample.1
        budget = sample.2
        mood = sample.3
        constraints = sample.4
        steps = makeSteps()
        save()
    }

    func resetMemory() {
        savedTrips = []
        memory = []
        trips = []
        activeTripID = nil
        runState = .idle
        steps = makeSteps()
        stateStore.clear()
    }

    private func makeSteps() -> [RunStep] {
        let memoryDetail = memory.isEmpty
            ? "No saved preferences yet"
            : "Loaded \(memory.count) saved preference\(memory.count == 1 ? "" : "s")"

        return [
            RunStep(
                title: "Understand trip brief",
                detail: "\(origin) to \(destination), \(mood.rawValue.lowercased()) pace, \(dollars(budget)) ceiling",
                tag: "reason",
                symbol: "sparkle.magnifyingglass"
            ),
            RunStep(
                title: "Search fare inventory",
                detail: "searchFlights(origin, destination, dates, budget)",
                tag: "tool call",
                symbol: "airplane.departure"
            ),
            RunStep(
                title: "Compose itinerary",
                detail: "buildItinerary(fares, constraints, memory)",
                tag: "tool call",
                symbol: "map"
            ),
            RunStep(
                title: "Update state",
                detail: memoryDetail,
                tag: "memory",
                symbol: "externaldrive"
            )
        ]
    }

    private func updateMemory(bestTrip: TripOption) {
        guard rememberPreferences else { return }

        memory = [
            MemoryNote(
                title: "Travel preference",
                detail: "\(origin) departures, \(mood.rawValue.lowercased()) trips, \(dollars(budget)) budget ceiling."
            ),
            MemoryNote(
                title: "Constraint",
                detail: constraints.isEmpty ? "No extra constraints saved." : constraints
            ),
            MemoryNote(
                title: "Last best option",
                detail: "\(bestTrip.name) to \(destination) at \(dollars(bestTrip.fare))."
            )
        ]
    }

    private func save() {
        let state = PersistedAgentState(
            origin: origin,
            destination: destination,
            departDate: departDate,
            returnDate: returnDate,
            budget: budget,
            constraints: constraints,
            rememberPreferences: rememberPreferences,
            mood: mood,
            savedTrips: savedTrips,
            memory: memory,
            activeTripID: activeTripID
        )

        stateStore.save(state)
    }

    private func load() {
        guard let state = stateStore.load() else { return }

        origin = state.origin
        destination = state.destination
        departDate = state.departDate
        returnDate = state.returnDate
        budget = state.budget
        constraints = state.constraints
        rememberPreferences = state.rememberPreferences
        mood = state.mood
        savedTrips = state.savedTrips
        memory = state.memory
        activeTripID = state.activeTripID
    }
}
