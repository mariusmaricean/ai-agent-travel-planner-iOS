import Foundation

enum TravelPlannerAPIError: LocalizedError, Sendable {
    case invalidResponse
    case serverError(Int)
    case emptyBaseURL
    case runFailed(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "The travel planner server returned an invalid response."
        case let .serverError(statusCode):
            "The travel planner server returned status \(statusCode)."
        case .emptyBaseURL:
            "Set TRAVEL_PLANNER_API_BASE_URL before using the live travel planner service."
        case let .runFailed(message):
            message
        }
    }
}

struct TravelPlannerAPIService: TravelPlanningServicing, Sendable {
    private let baseURL: URL
    private let session: URLSession

    init(
        baseURL: URL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    func makePlan(
        for brief: TripBrief,
        progress: TravelPlanningProgressHandler?
    ) async throws -> TripPlanResult {
        var deliveredEventIDs = Set<Int>()
        var snapshot = try await startRun(for: brief)
        deliveredEventIDs = await publishProgress(
            from: snapshot,
            deliveredEventIDs: deliveredEventIDs,
            progress: progress
        )

        while snapshot.isRunning {
            try await Task.sleep(for: .milliseconds(450))
            snapshot = try await fetchRunEvents(runID: snapshot.runId)
            deliveredEventIDs = await publishProgress(
                from: snapshot,
                deliveredEventIDs: deliveredEventIDs,
                progress: progress
            )
        }

        if snapshot.isCompleted, let result = snapshot.result {
            return result.result()
        }

        if snapshot.isFailed {
            throw TravelPlannerAPIError.runFailed(snapshot.error ?? "The agent run failed.")
        }

        throw TravelPlannerAPIError.invalidResponse
    }

    private func startRun(for brief: TripBrief) async throws -> TripPlanRunSnapshotPayload {
        let request = try makeRequest(for: brief)
        let data = try await responseData(for: request)
        return try JSONDecoder().decode(TripPlanRunSnapshotPayload.self, from: data)
    }

    private func fetchRunEvents(runID: String) async throws -> TripPlanRunSnapshotPayload {
        let endpoint = baseURL
            .appending(path: "trip-plans")
            .appending(path: "runs")
            .appending(path: runID)
            .appending(path: "events")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let data = try await responseData(for: request)
        return try JSONDecoder().decode(TripPlanRunSnapshotPayload.self, from: data)
    }

    private func responseData(for request: URLRequest) async throws -> Data {
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw TravelPlannerAPIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw TravelPlannerAPIError.serverError(httpResponse.statusCode)
        }

        return data
    }

    private func publishProgress(
        from snapshot: TripPlanRunSnapshotPayload,
        deliveredEventIDs: Set<Int>,
        progress: TravelPlanningProgressHandler?
    ) async -> Set<Int> {
        var updatedEventIDs = deliveredEventIDs

        for event in snapshot.events where !updatedEventIDs.contains(event.id) {
            updatedEventIDs.insert(event.id)
            guard let progressEvent = event.progressEvent() else { continue }
            await progress?(progressEvent)
        }

        return updatedEventIDs
    }

    private func makeRequest(for brief: TripBrief) throws -> URLRequest {
        let endpoint = baseURL
            .appending(path: "trip-plans")
            .appending(path: "runs")
        let dateFormatter = ISO8601DateFormatter()
        dateFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(TripPlanRequest(brief: brief, dateFormatter: dateFormatter))
        return request
    }
}
