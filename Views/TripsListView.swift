import SwiftUI

enum TripsMode {
    case results
    case saved
}

struct TripsListView: View {
    @ObservedObject var viewModel: AgentViewModel
    var mode: TripsMode
    @State private var detailTrip: TripOption?

    var trips: [TripOption] {
        switch mode {
        case .results:
            viewModel.trips
        case .saved:
            viewModel.savedTrips
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                SectionHeader(
                    title: title,
                    subtitle: subtitle
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
                EmptyStateView(text: emptyText)
            } else {
                ForEach(trips) { trip in
                    TripCard(
                        trip: trip,
                        isActive: viewModel.isTripActive(trip),
                        isSaved: viewModel.isTripSaved(trip),
                        onSelect: { viewModel.selectTrip(trip) },
                        onSave: { viewModel.saveTrip(trip) },
                        onDetails: { detailTrip = trip }
                    )
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .sheet(item: $detailTrip) { trip in
            TripDetailView(viewModel: viewModel, trip: trip)
        }
    }

    private var title: String {
        switch mode {
        case .results:
            "Results"
        case .saved:
            "Saved Trips"
        }
    }

    private var subtitle: String {
        if trips.isEmpty {
            return mode == .results ? "Run the agent first" : "Save a result to keep it here"
        }

        switch mode {
        case .results:
            return "\(trips.count) option\(trips.count == 1 ? "" : "s") ready"
        case .saved:
            return "\(trips.count) saved locally"
        }
    }

    private var emptyText: String {
        switch mode {
        case .results:
            "No generated trips yet."
        case .saved:
            "No trips saved yet."
        }
    }
}

struct TripDetailView: View {
    @ObservedObject var viewModel: AgentViewModel
    var trip: TripOption
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    detailHeader
                    metrics
                    itinerary
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(TravelPlannerColor.paper.ignoresSafeArea())
            .navigationTitle("Trip Detail")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                actionBar
            }
        }
    }

    private var detailHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(trip.name)
                .font(.title2.weight(.bold))

            Text(trip.route)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Text(trip.meta)
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var metrics: some View {
        HStack(spacing: 10) {
            MetricCard(value: dollars(trip.fare), label: "Fare", color: TravelPlannerColor.tealSoft)
            MetricCard(value: "\(trip.score)", label: "Score", color: TravelPlannerColor.goldSoft)
            MetricCard(value: "\(trip.days.count)", label: "Days", color: TravelPlannerColor.limeSoft)
        }
    }

    private var itinerary: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Itinerary", subtitle: "\(trip.days.count) planned stop\(trip.days.count == 1 ? "" : "s")")

            ForEach(trip.days) { day in
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(day.label)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(width: 34, height: 34)
                            .background(TravelPlannerColor.teal, in: Circle())

                        Text(day.title)
                            .font(.headline)
                    }

                    Text(day.detail)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
        }
    }

    private var actionBar: some View {
        HStack(spacing: 10) {
            Button {
                viewModel.selectTrip(trip)
            } label: {
                Label("Select", systemImage: "checkmark.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)

            if viewModel.isTripSaved(trip) {
                Button(role: .destructive) {
                    viewModel.removeSavedTrip(trip)
                    dismiss()
                } label: {
                    Label("Remove", systemImage: "trash")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            } else {
                Button {
                    viewModel.saveTrip(trip)
                } label: {
                    Label("Save Trip", systemImage: "tray.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(TravelPlannerColor.teal)
            }
        }
        .padding(16)
        .background(.ultraThinMaterial)
    }
}
