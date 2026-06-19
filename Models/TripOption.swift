import Foundation

struct TripDay: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var label: String
    var title: String
    var detail: String
}

struct TripOption: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var name: String
    var route: String
    var fare: Double
    var score: Int
    var meta: String
    var days: [TripDay]
}
