import Foundation

enum StepStatus: String, Codable, Sendable {
    case queued
    case active
    case done
}

struct RunStep: Identifiable, Codable, Sendable {
    var id = UUID()
    var title: String
    var detail: String
    var tag: String
    var symbol: String
    var status: StepStatus = .queued
}
