import Foundation

enum AgentRunState: Equatable, Sendable {
    case idle
    case running
    case done
    case failed(String)

    var title: String {
        switch self {
        case .idle:
            "Idle"
        case .running:
            "Running"
        case .done:
            "Done"
        case .failed:
            "Failed"
        }
    }

    var errorMessage: String? {
        guard case let .failed(message) = self else { return nil }
        return message
    }

    var isRunning: Bool {
        self == .running
    }
}
