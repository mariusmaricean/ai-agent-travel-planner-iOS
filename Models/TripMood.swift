import Foundation

enum TripMood: String, CaseIterable, Codable, Identifiable, Sendable {
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
