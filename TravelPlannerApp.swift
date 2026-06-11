import SwiftUI

@main
struct TravelPlannerApp: App {
    var body: some Scene {
        WindowGroup {
            AgentHomeView()
        }
    }
}

enum TripMood: String, CaseIterable, Codable, Identifiable {
    case culture = "Culture"
    case food = "Food"
    case recharge = "Recharge"

    var id: String { rawValue }

    var symbol: String {
        switch self {
        case .culture: "building.columns"
        case .food: "fork.knife"
        case .recharge: "leaf"
        }
    }

    var focusItems: [String] {
        switch self {
        case .culture:
            ["tile museum", "old town walk", "riverfront concert"]
        case .food:
            ["market crawl", "chef counter", "dessert stop"]
        case .recharge:
            ["spa morning", "garden walk", "slow cafe"]
        }
    }
}

enum StepStatus: String, Codable {
    case queued
    case active
    case done
}

struct RunStep: Identifiable, Codable {
    var id = UUID()
    var title: String
    var detail: String
    var tag: String
    var symbol: String
    var status: StepStatus = .queued
}

struct TripDay: Identifiable, Codable, Hashable {
    var id = UUID()
    var label: String
    var title: String
    var detail: String
}

struct TripOption: Identifiable, Codable, Hashable {
    var id = UUID()
    var name: String
    var route: String
    var fare: Double
    var score: Int
    var meta: String
    var days: [TripDay]
}

struct MemoryNote: Identifiable, Codable, Hashable {
    var id = UUID()
    var title: String
    var detail: String
}

struct PersistedAgentState: Codable {
    var origin: String
    var destination: String
    var departDate: Date
    var returnDate: Date
    var budget: Double
    var constraints: String
    var rememberPreferences: Bool
    var mood: TripMood
    var savedTrips: [TripOption]
    var memory: [MemoryNote]
    var activeTripID: UUID?
}

@MainActor
final class AgentStore: ObservableObject {
    @Published var origin = "New York"
    @Published var destination = "Lisbon"
    @Published var departDate = Calendar.current.date(byAdding: .day, value: 22, to: Date()) ?? Date()
    @Published var returnDate = Calendar.current.date(byAdding: .day, value: 27, to: Date()) ?? Date()
    @Published var budget = 1_400.0
    @Published var constraints = "Window seat, no red-eye flights, one free evening, save anything that beats the budget."
    @Published var rememberPreferences = true
    @Published var mood: TripMood = .culture
    @Published var runStatus = "Idle"
    @Published var steps: [RunStep] = []
    @Published var trips: [TripOption] = []
    @Published var savedTrips: [TripOption] = []
    @Published var memory: [MemoryNote] = []
    @Published var activeTripID: UUID?
    @Published var isRunning = false

    private let storageKey = "travel-planner-ios-state-v1"

    init() {
        load()
        steps = makeSteps()
    }

    var savedCount: Int {
        savedTrips.count
    }

    var visibleTrips: [TripOption] {
        trips.isEmpty ? savedTrips : trips
    }

    var duration: Int {
        let days = Calendar.current.dateComponents([.day], from: departDate, to: returnDate).day ?? 5
        return min(max(days, 3), 10)
    }

    func runAgent() async {
        guard !isRunning else { return }

        isRunning = true
        runStatus = "Running"
        trips = []
        steps = makeSteps()

        for index in steps.indices {
            steps[index].status = .active
            try? await Task.sleep(nanoseconds: 520_000_000)
            steps[index].status = .done
        }

        let generated = makeTrips()
        trips = generated
        activeTripID = generated.first?.id
        if let bestTrip = generated.first {
            updateMemory(bestTrip: bestTrip)
        }
        runStatus = "Done"
        isRunning = false
        save()
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
        runStatus = "Idle"
        steps = makeSteps()
        UserDefaults.standard.removeObject(forKey: storageKey)
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

    private func makeTrips() -> [TripOption] {
        let route = "\(origin) -> \(destination)"
        let baseFare = max(320, (budget * 0.42).rounded())
        let focus = mood.focusItems

        return [
            TripOption(
                name: "Balanced Sprint",
                route: route,
                fare: baseFare + 70,
                score: 94,
                meta: "\(duration) days | morning outbound | 1 checked bag",
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
                meta: "\(duration) days | one connection | budget winner",
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
                meta: "\(duration) days | direct flight | aisle-friendly timing",
                days: [
                    TripDay(label: "D1", title: "Direct arrival", detail: "Midday landing, easy transfer, no late-night commitments."),
                    TripDay(label: "D2", title: "Prime slot", detail: "\(focus[1]) anchored by the highest-fit booking window."),
                    TripDay(label: "D3", title: "Buffer day", detail: "\(focus[2]) with an airport transfer already staged.")
                ]
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

        guard let data = try? JSONEncoder().encode(state) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }

    private func load() {
        guard
            let data = UserDefaults.standard.data(forKey: storageKey),
            let state = try? JSONDecoder().decode(PersistedAgentState.self, from: data)
        else {
            return
        }

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

struct AgentHomeView: View {
    @StateObject private var store = AgentStore()
    @State private var selectedTab: AgentTab = .brief

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        HeroView(store: store)
                        BriefFormView(store: store)
                    }
                    .padding(16)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Travel Planner")
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            store.loadSample()
                        } label: {
                            Label("Load sample", systemImage: "shuffle")
                        }
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button(role: .destructive) {
                            store.resetMemory()
                        } label: {
                            Label("Reset memory", systemImage: "arrow.counterclockwise")
                        }
                    }
                }
            }
            .tabItem {
                Label("Brief", systemImage: "square.and.pencil")
            }
            .tag(AgentTab.brief)

            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        RunTimelineView(store: store)
                        TripsListView(store: store, mode: .results)
                    }
                    .padding(16)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Run")
            }
            .tabItem {
                Label("Run", systemImage: "waveform.path.ecg")
            }
            .tag(AgentTab.run)

            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        TripsListView(store: store, mode: .saved)
                        MemoryView(store: store)
                    }
                    .padding(16)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Saved")
            }
            .tabItem {
                Label("Saved", systemImage: "tray.full")
            }
            .tag(AgentTab.saved)
        }
        .tint(TravelPlannerColor.teal)
    }
}

enum AgentTab {
    case brief
    case run
    case saved
}

struct HeroView: View {
    @ObservedObject var store: AgentStore

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Image("TravelPlannerHero")
                .resizable()
                .scaledToFill()
                .frame(height: 258)
                .clipped()

            LinearGradient(
                colors: [.black.opacity(0.68), .black.opacity(0.16), .black.opacity(0.82)],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 8) {
                    Image(systemName: "sparkles")
                    Text("Autonomous travel run")
                        .font(.caption.weight(.semibold))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(.white.opacity(0.16), in: Capsule())

                Spacer()

                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Plan the next move.")
                            .font(.system(size: 40, weight: .black, design: .rounded))
                            .foregroundStyle(.white)
                            .lineLimit(2)
                            .minimumScaleFactor(0.75)

                        Text("Flights, days, constraints, and saved state in one agent pass.")
                            .font(.subheadline)
                            .foregroundStyle(.white.opacity(0.82))
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 10)

                    StatusChip(text: store.runStatus)
                }
            }
            .padding(16)
        }
        .frame(height: 258)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .shadow(color: .black.opacity(0.14), radius: 18, y: 12)
        .accessibilityElement(children: .combine)
    }
}

struct BriefFormView: View {
    @ObservedObject var store: AgentStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(title: "Trip Brief", subtitle: "\(store.origin) to \(store.destination)")

            Picker("Mood", selection: $store.mood) {
                ForEach(TripMood.allCases) { mood in
                    Label(mood.rawValue, systemImage: mood.symbol)
                        .tag(mood)
                }
            }
            .pickerStyle(.segmented)

            HStack(spacing: 12) {
                FieldCard(title: "From") {
                    TextField("Origin", text: $store.origin)
                        .textInputAutocapitalization(.words)
                }

                FieldCard(title: "To") {
                    TextField("Destination", text: $store.destination)
                        .textInputAutocapitalization(.words)
                }
            }

            HStack(spacing: 12) {
                FieldCard(title: "Depart") {
                    DatePicker("Depart", selection: $store.departDate, displayedComponents: .date)
                        .labelsHidden()
                }

                FieldCard(title: "Return") {
                    DatePicker("Return", selection: $store.returnDate, displayedComponents: .date)
                        .labelsHidden()
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Label("Budget per person", systemImage: "creditcard")
                    Spacer()
                    Text(dollars(store.budget))
                        .font(.headline)
                        .foregroundStyle(TravelPlannerColor.coral)
                }

                Slider(value: $store.budget, in: 600...3_200, step: 100)
                    .tint(TravelPlannerColor.coral)
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            VStack(alignment: .leading, spacing: 8) {
                Label("Constraints", systemImage: "slider.horizontal.3")
                    .font(.subheadline.weight(.semibold))

                TextEditor(text: $store.constraints)
                    .frame(minHeight: 92)
                    .scrollContentBackground(.hidden)
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            Toggle(isOn: $store.rememberPreferences) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Remember preferences")
                        .font(.subheadline.weight(.semibold))
                    Text("Use saved notes during the next run")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            Button {
                Task { await store.runAgent() }
            } label: {
                HStack {
                    if store.isRunning {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Image(systemName: "arrow.right")
                    }
                    Text(store.isRunning ? "Running agent" : "Run agent")
                }
                .font(.headline)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
            }
            .buttonStyle(.borderedProminent)
            .tint(.black)
            .disabled(store.isRunning)
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct RunTimelineView: View {
    @ObservedObject var store: AgentStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Agent Run",
                subtitle: store.isRunning ? "Agent is acting" : "\(store.steps.filter { $0.status == .done }.count) actions completed"
            )

            HStack(spacing: 10) {
                MetricCard(value: "\(store.steps.count)", label: "steps", color: TravelPlannerColor.tealSoft)
                MetricCard(value: "3", label: "calls", color: TravelPlannerColor.limeSoft)
                MetricCard(value: "\(store.savedCount)", label: "saved", color: TravelPlannerColor.goldSoft)
            }

            VStack(spacing: 10) {
                ForEach(store.steps) { step in
                    RunStepRow(step: step)
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

enum TripsMode {
    case results
    case saved
}

struct TripsListView: View {
    @ObservedObject var store: AgentStore
    var mode: TripsMode

    var trips: [TripOption] {
        switch mode {
        case .results:
            store.visibleTrips
        case .saved:
            store.savedTrips
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                SectionHeader(
                    title: mode == .results ? "Results" : "Saved Trips",
                    subtitle: trips.isEmpty ? "Run the agent first" : "\(trips.count) option\(trips.count == 1 ? "" : "s") ready"
                )

                Spacer()

                if mode == .results {
                    Button {
                        store.saveBestTrip()
                    } label: {
                        Image(systemName: "square.and.arrow.down")
                    }
                    .buttonStyle(.bordered)
                    .tint(TravelPlannerColor.teal)
                    .disabled(trips.isEmpty)
                }
            }

            if trips.isEmpty {
                EmptyStateView(text: "No trips saved yet.")
            } else {
                ForEach(trips) { trip in
                    TripCard(
                        trip: trip,
                        isActive: store.activeTripID == trip.id,
                        isSaved: store.savedTrips.contains(where: { $0.id == trip.id }),
                        onSelect: { store.selectTrip(trip) },
                        onSave: { store.saveTrip(trip) }
                    )
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct MemoryView: View {
    @ObservedObject var store: AgentStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Memory",
                subtitle: store.memory.isEmpty ? "Preference state" : "\(store.memory.count) saved notes"
            )

            if store.memory.isEmpty {
                EmptyStateView(text: "Memory is empty.")
            } else {
                ForEach(store.memory) { note in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "brain.head.profile")
                            .foregroundStyle(TravelPlannerColor.coral)
                            .frame(width: 34, height: 34)
                            .background(TravelPlannerColor.coralSoft, in: Circle())

                        VStack(alignment: .leading, spacing: 4) {
                            Text(note.title)
                                .font(.subheadline.weight(.semibold))
                            Text(note.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(12)
                    .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct TripCard: View {
    var trip: TripOption
    var isActive: Bool
    var isSaved: Bool
    var onSelect: () -> Void
    var onSave: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(trip.name)
                        .font(.headline)
                    Text("\(trip.route) | score \(trip.score)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(trip.meta)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Text(dollars(trip.fare))
                    .font(.headline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 8)
                    .background(TravelPlannerColor.teal, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            VStack(spacing: 8) {
                ForEach(trip.days) { day in
                    HStack(alignment: .top, spacing: 10) {
                        Text(day.label)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(width: 34, height: 34)
                            .background(TravelPlannerColor.gold, in: Circle())

                        VStack(alignment: .leading, spacing: 2) {
                            Text(day.title)
                                .font(.subheadline.weight(.semibold))
                            Text(day.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Spacer()
                    }
                    .padding(10)
                    .background(TravelPlannerColor.paper, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }

            HStack(spacing: 10) {
                Button(action: onSelect) {
                    Label("Select", systemImage: "checkmark.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                Button(action: onSave) {
                    Label(isSaved ? "Saved" : "Save", systemImage: isSaved ? "checkmark" : "tray.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(isSaved ? TravelPlannerColor.coral : TravelPlannerColor.teal)
            }
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(isActive ? TravelPlannerColor.teal.opacity(0.55) : Color.black.opacity(0.06), lineWidth: isActive ? 2 : 1)
        }
    }
}

struct RunStepRow: View {
    var step: RunStep

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: step.status == .done ? "checkmark" : step.symbol)
                .foregroundStyle(iconColor)
                .frame(width: 36, height: 36)
                .background(iconBackground, in: Circle())

            VStack(alignment: .leading, spacing: 3) {
                Text(step.title)
                    .font(.subheadline.weight(.semibold))
                Text(step.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()

            Text(step.tag)
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(TravelPlannerColor.paper, in: Capsule())
        }
        .padding(12)
        .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var iconColor: Color {
        switch step.status {
        case .queued: .secondary
        case .active: .white
        case .done: .white
        }
    }

    private var iconBackground: Color {
        switch step.status {
        case .queued: TravelPlannerColor.paper
        case .active: TravelPlannerColor.teal
        case .done: TravelPlannerColor.lime
        }
    }
}

struct FieldCard<Content: View>: View {
    var title: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
            content
                .font(.body.weight(.semibold))
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct SectionHeader: View {
    var title: String
    var subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct MetricCard: View {
    var value: String
    var label: String
    var color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.weight(.black))
            Text(label.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 74)
        .background(color, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct StatusChip: View {
    var text: String

    var body: some View {
        VStack(spacing: 3) {
            Text(text)
                .font(.headline.weight(.black))
            Text("Agent")
                .font(.caption2.weight(.bold))
                .textCase(.uppercase)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(TravelPlannerColor.teal.opacity(0.95), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct EmptyStateView: View {
    var text: String

    var body: some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity)
            .padding(18)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

enum TravelPlannerColor {
    static let paper = Color(red: 0.98, green: 0.97, blue: 0.94)
    static let teal = Color(red: 0.06, green: 0.46, blue: 0.43)
    static let tealSoft = Color(red: 0.85, green: 0.94, blue: 0.93)
    static let coral = Color(red: 0.90, green: 0.37, blue: 0.31)
    static let coralSoft = Color(red: 1.00, green: 0.88, blue: 0.85)
    static let gold = Color(red: 0.78, green: 0.54, blue: 0.07)
    static let goldSoft = Color(red: 1.00, green: 0.94, blue: 0.84)
    static let lime = Color(red: 0.55, green: 0.71, blue: 0.27)
    static let limeSoft = Color(red: 0.93, green: 0.96, blue: 0.86)
}

enum TravelPlannerFormat {
    static let currency: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.maximumFractionDigits = 0
        return formatter
    }()
}

func dollars(_ value: Double) -> String {
    TravelPlannerFormat.currency.string(from: NSNumber(value: value)) ?? "$\(Int(value))"
}
