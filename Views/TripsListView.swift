import SwiftUI

enum TripsMode {
    case results
    case saved
}

struct TripsListView: View {
    @ObservedObject var viewModel: AgentViewModel
    var mode: TripsMode

    var trips: [TripOption] {
        switch mode {
        case .results:
            viewModel.visibleTrips
        case .saved:
            viewModel.savedTrips
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                SectionHeader(
                    title: mode == .results ? "Results" : "Saved Trips",
                    subtitle: trips.isEmpty ? "Run the agent first" : "\(trips.count) option\(trips.count == 1 ? "" : "s") ready"
                )

                Spacer()

                if mode == .results {
                    Button {
                        viewModel.saveBestTrip()
                    } label: {
                        Image(systemName: "square.and.arrow.down")
                    }
                    .buttonStyle(.bordered)
                    .tint(TravelPlannerColor.teal)
                    .disabled(trips.isEmpty)
                }
            }

            if trips.isEmpty {
                EmptyStateView(text: "No trips saved yet.")
            } else {
                ForEach(trips) { trip in
                    TripCard(
                        trip: trip,
                        isActive: viewModel.activeTripID == trip.id,
                        isSaved: viewModel.savedTrips.contains(where: { $0.id == trip.id }),
                        onSelect: { viewModel.selectTrip(trip) },
                        onSave: { viewModel.saveTrip(trip) }
                    )
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
