import Foundation

struct TripBrief: Sendable {
    var origin: String
    var destination: String
    var departDate: Date
    var returnDate: Date
    var budget: Double
    var constraints: String
    var rememberPreferences: Bool
    var mood: TripMood
    var memory: [MemoryNote]

    var duration: Int {
        let days = Calendar.current.dateComponents([.day], from: departDate, to: returnDate).day ?? 5
        return min(max(days, 3), 10)
    }
}
