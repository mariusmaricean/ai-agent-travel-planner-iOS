import Foundation

struct TripPlanRequest: Encodable, Sendable {
    var origin: String
    var destination: String
    var departDate: String
    var returnDate: String
    var budget: Double
    var constraints: String
    var rememberPreferences: Bool
    var mood: String
    var memory: [MemoryNotePayload]

    init(brief: TripBrief, dateFormatter: ISO8601DateFormatter) {
        origin = brief.origin
        destination = brief.destination
        departDate = dateFormatter.string(from: brief.departDate)
        returnDate = dateFormatter.string(from: brief.returnDate)
        budget = brief.budget
        constraints = brief.constraints
        rememberPreferences = brief.rememberPreferences
        mood = brief.mood.rawValue
        memory = brief.memory.map(MemoryNotePayload.init(note:))
    }
}

struct TripPlanResponse: Decodable, Sendable {
    var trips: [TripOptionPayload]
    var memory: [MemoryNotePayload]?

    func result() -> TripPlanResult {
        TripPlanResult(
            trips: trips.map { $0.tripOption() },
            memory: memory?.map { $0.memoryNote() }
        )
    }
}

struct TripPlanRunSnapshotPayload: Decodable, Sendable {
    var runId: String
    var status: String
    var events: [AgentRunEventPayload]
    var result: TripPlanResponse?
    var error: String?

    var isRunning: Bool {
        status == "running"
    }

    var isCompleted: Bool {
        status == "completed"
    }

    var isFailed: Bool {
        status == "failed"
    }
}

struct SavedTripPlanPayload: Decodable, Sendable {
    var id: String
    var response: TripPlanResponse

    func result() -> TripPlanResult {
        response.result()
    }
}

struct AgentRunEventPayload: Decodable, Sendable {
    var id: Int
    var step: String
    var status: String
    var title: String
    var detail: String

    func progressEvent() -> AgentRunProgressEvent? {
        guard
            let step = AgentRunStep(rawValue: step),
            let status = StepStatus(rawValue: status)
        else {
            return nil
        }

        return AgentRunProgressEvent(
            step: step,
            status: status,
            title: title,
            detail: detail
        )
    }
}

struct TripOptionPayload: Decodable, Sendable {
    var name: String
    var route: String
    var fare: Double
    var score: Int
    var meta: String
    var days: [TripDayPayload]

    func tripOption() -> TripOption {
        TripOption(
            name: name,
            route: route,
            fare: fare,
            score: score,
            meta: meta,
            days: days.map { $0.tripDay() }
        )
    }
}

struct TripDayPayload: Decodable, Sendable {
    var label: String
    var title: String
    var detail: String

    func tripDay() -> TripDay {
        TripDay(label: label, title: title, detail: detail)
    }
}

struct MemoryNotePayload: Codable, Sendable {
    var title: String
    var detail: String

    init(title: String, detail: String) {
        self.title = title
        self.detail = detail
    }

    init(note: MemoryNote) {
        title = note.title
        detail = note.detail
    }

    func memoryNote() -> MemoryNote {
        MemoryNote(title: title, detail: detail)
    }
}
