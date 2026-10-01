import Foundation

struct TravelPlannerAccount: Codable, Equatable, Sendable {
    var id: String
    var email: String
    var displayName: String?
    var travelerId: String

    var displayTitle: String {
        guard let displayName, !displayName.isEmpty else {
            return email
        }

        return displayName
    }
}

struct TravelPlannerAccountSession: Codable, Equatable, Sendable {
    var accessToken: String
    var tokenType: String
    var user: TravelPlannerAccount

    var authorizationHeader: String {
        "\(tokenType.capitalized) \(accessToken)"
    }
}
