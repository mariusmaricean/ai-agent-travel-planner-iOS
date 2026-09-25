import Foundation

enum StepStatus: String, Codable, Sendable {
    case queued
    case active
    case done
    case failed
}

enum AgentRunStep: String, Codable, Sendable {
    case research
    case flights
    case itinerary
    case critic
    case revision
    case memory
}

struct RunStep: Identifiable, Codable, Sendable {
    var id = UUID()
    var key: AgentRunStep
    var title: String
    var detail: String
    var tag: String
    var symbol: String
    var status: StepStatus = .queued
}

struct AgentRunProgressEvent: Sendable {
    var step: AgentRunStep
    var status: StepStatus
    var title: String
    var detail: String
}
