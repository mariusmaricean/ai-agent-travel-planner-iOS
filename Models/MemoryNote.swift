import Foundation

struct MemoryNote: Identifiable, Codable, Hashable, Sendable {
    var id = UUID()
    var title: String
    var detail: String
}
