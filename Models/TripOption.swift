import Foundation

struct TripDay: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var label: String
    var title: String
    var detail: String
}

enum TripExecutionStatus: String, CaseIterable, Codable, Identifiable, Sendable {
    case draft = "Draft"
    case ready = "Ready"
    case booked = "Booked"

    var id: Self { self }
}

struct TripTask: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var title: String
    var isDone = false
}

struct TripOption: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var name: String
    var route: String
    var fare: Double
    var score: Int
    var meta: String
    var days: [TripDay]
    var executionStatus: TripExecutionStatus = .draft
    var notes: String = ""
    var tasks: [TripTask] = []

    init(
        id: UUID = UUID(),
        name: String,
        route: String,
        fare: Double,
        score: Int,
        meta: String,
        days: [TripDay],
        executionStatus: TripExecutionStatus = .draft,
        notes: String = "",
        tasks: [TripTask] = []
    ) {
        self.id = id
        self.name = name
        self.route = route
        self.fare = fare
        self.score = score
        self.meta = meta
        self.days = days
        self.executionStatus = executionStatus
        self.notes = notes
        self.tasks = tasks
    }

    func matchesSavedTrip(_ trip: TripOption) -> Bool {
        name == trip.name
            && route == trip.route
            && fare == trip.fare
            && meta == trip.meta
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case route
        case fare
        case score
        case meta
        case days
        case executionStatus
        case notes
        case tasks
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        id = try container.decodeIfPresent(UUID.self, forKey: .id) ?? UUID()
        name = try container.decode(String.self, forKey: .name)
        route = try container.decode(String.self, forKey: .route)
        fare = try container.decode(Double.self, forKey: .fare)
        score = try container.decode(Int.self, forKey: .score)
        meta = try container.decode(String.self, forKey: .meta)
        days = try container.decode([TripDay].self, forKey: .days)
        executionStatus = try container.decodeIfPresent(TripExecutionStatus.self, forKey: .executionStatus) ?? .draft
        notes = try container.decodeIfPresent(String.self, forKey: .notes) ?? ""
        tasks = try container.decodeIfPresent([TripTask].self, forKey: .tasks) ?? []
    }
}
