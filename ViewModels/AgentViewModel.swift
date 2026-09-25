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

    var runStatus: String {
        runState.title
    }

    var completedStepCount: Int {
        steps.filter { $0.status == .done }.count
    }

    var agentStageCount: Int {
        3
    }

    var timelineSubtitle: String {
        if let activeStep = steps.first(where: { $0.status == .active }) {
            return activeStep.title
        }

        if case .failed = runState {
            return "Agent stopped before final result"
        }

        return "\(completedStepCount) actions completed"
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
        let progressTask = Task { await animateAgentProgress() }

        do {
            let result = try await planningService.makePlan(for: currentBrief)
            progressTask.cancel()
            finishProgress()
            trips = result.trips
            activeTripID = result.trips.first?.id
            applyMemory(from: result)
            runState = .done
            save()
        } catch {
            progressTask.cancel()
            failProgress()
            runState = .failed(error.localizedDescription)
        }
    }

    private func animateAgentProgress() async {
        for index in steps.indices {
            guard !Task.isCancelled else { return }

            activateStep(at: index)

            do {
                try await Task.sleep(for: .milliseconds(560))
            } catch {
                return
            }

            guard !Task.isCancelled else { return }
            completeStep(at: index)
        }
    }

    private func activateStep(at index: Int) {
        guard steps.indices.contains(index) else { return }

        for stepIndex in steps.indices where stepIndex < index && steps[stepIndex].status != .failed {
            steps[stepIndex].status = .done
        }

        if steps[index].status == .queued {
            steps[index].status = .active
        }
    }

    private func completeStep(at index: Int) {
        guard steps.indices.contains(index), steps[index].status == .active else { return }
        steps[index].status = .done
    }

    private func finishProgress() {
        for index in steps.indices {
            steps[index].status = .done
        }
    }

    private func failProgress() {
        if let activeIndex = steps.firstIndex(where: { $0.status == .active }) {
            steps[activeIndex].status = .failed
            return
        }

        if let queuedIndex = steps.firstIndex(where: { $0.status == .queued }) {
            steps[queuedIndex].status = .failed
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
        if let savedTrip = savedTrip(matching: trip) {
            activeTripID = savedTrip.id
            save()
            return
        }

        savedTrips.insert(trip, at: 0)
        activeTripID = trip.id
        save()
    }

    func saveBestTrip() {
        guard let bestTrip = trips.first ?? savedTrips.first else { return }
        saveTrip(bestTrip)
    }

    func selectTrip(_ trip: TripOption) {
        activeTripID = savedTrip(matching: trip)?.id ?? trip.id
        save()
    }

    func removeSavedTrip(_ trip: TripOption) {
        let wasActive = isTripActive(trip)

        savedTrips.removeAll { savedTrip in
            savedTrip.id == trip.id || savedTrip.matchesSavedTrip(trip)
        }

        if wasActive {
            activeTripID = trips.first?.id ?? savedTrips.first?.id
        }

        save()
    }

    func isTripSaved(_ trip: TripOption) -> Bool {
        savedTrip(matching: trip) != nil
    }

    func savedVersion(of trip: TripOption) -> TripOption {
        savedTrip(matching: trip) ?? trip
    }

    func executionStatus(for trip: TripOption) -> TripExecutionStatus? {
        savedTrip(matching: trip)?.executionStatus
    }

    func isTripActive(_ trip: TripOption) -> Bool {
        if activeTripID == trip.id {
            return true
        }

        guard let activeTrip = savedTrips.first(where: { $0.id == activeTripID }) else {
            return false
        }

        return activeTrip.matchesSavedTrip(trip)
    }

    func updateExecutionStatus(_ status: TripExecutionStatus, for trip: TripOption) {
        updateSavedTrip(matching: trip) { savedTrip in
            savedTrip.executionStatus = status
        }
    }

    func updateNotes(_ notes: String, for trip: TripOption) {
        updateSavedTrip(matching: trip) { savedTrip in
            savedTrip.notes = notes
        }
    }

    func addTask(title: String, to trip: TripOption) {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else { return }

        updateSavedTrip(matching: trip) { savedTrip in
            savedTrip.tasks.append(TripTask(title: trimmedTitle))
        }
    }

    func toggleTask(_ task: TripTask, for trip: TripOption) {
        updateSavedTrip(matching: trip) { savedTrip in
            guard let index = savedTrip.tasks.firstIndex(where: { $0.id == task.id }) else { return }
            savedTrip.tasks[index].isDone.toggle()
        }
    }

    func removeTask(_ task: TripTask, from trip: TripOption) {
        updateSavedTrip(matching: trip) { savedTrip in
            savedTrip.tasks.removeAll { $0.id == task.id }
        }
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
                title: "Research destination",
                detail: "DestinationResearchAgent studies \(destination), \(mood.rawValue.lowercased()) goals, constraints, and memory",
                tag: "research",
                symbol: "binoculars"
            ),
            RunStep(
                title: "Search flights",
                detail: "TravelPlanningToolRouter.search_flights() checks route, dates, and \(dollars(budget)) ceiling",
                tag: "tool call",
                symbol: "airplane.departure"
            ),
            RunStep(
                title: "Build itinerary",
                detail: "ItineraryAgent turns fares and destination research into trip options",
                tag: "planning",
                symbol: "map"
            ),
            RunStep(
                title: "Critic review",
                detail: "ItineraryCriticAgent checks budget, constraints, pacing, and missing days",
                tag: "guardrail",
                symbol: "checklist"
            ),
            RunStep(
                title: "Revise if needed",
                detail: "Rejected plans go through ItineraryAgent.revise() before the final response",
                tag: "feedback",
                symbol: "arrow.triangle.2.circlepath"
            ),
            RunStep(
                title: "Finalize memory",
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

    private func savedTrip(matching trip: TripOption) -> TripOption? {
        savedTrips.first { savedTrip in
            savedTrip.id == trip.id || savedTrip.matchesSavedTrip(trip)
        }
    }

    private func updateSavedTrip(
        matching trip: TripOption,
        update: (inout TripOption) -> Void
    ) {
        if let index = savedTrips.firstIndex(where: { $0.id == trip.id || $0.matchesSavedTrip(trip) }) {
            update(&savedTrips[index])
            activeTripID = savedTrips[index].id
            save()
            return
        }

        var savedTrip = trip
        update(&savedTrip)
        savedTrips.insert(savedTrip, at: 0)
        activeTripID = savedTrip.id
        save()
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
