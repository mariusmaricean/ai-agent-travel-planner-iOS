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
                        executionStatus: executionStatus(for: trip),
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

    private func executionStatus(for trip: TripOption) -> TripExecutionStatus? {
        switch mode {
        case .results:
            viewModel.executionStatus(for: trip)
        case .saved:
            trip.executionStatus
        }
    }
}

struct TripDetailView: View {
    @ObservedObject var viewModel: AgentViewModel
    var trip: TripOption
    @Environment(\.dismiss) private var dismiss
    @State private var newTaskTitle = ""

    private var currentTrip: TripOption {
        viewModel.savedVersion(of: trip)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    detailHeader
                    metrics
                    executionPanel
                    notesPanel
                    tasksPanel
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
            HStack(alignment: .top, spacing: 12) {
                Text(currentTrip.name)
                    .font(.title2.weight(.bold))
                    .frame(maxWidth: .infinity, alignment: .leading)

                Label(currentTrip.executionStatus.rawValue, systemImage: currentTrip.executionStatus.symbol)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(currentTrip.executionStatus.tint)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(currentTrip.executionStatus.background, in: Capsule())
            }

            Text(currentTrip.route)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Text(currentTrip.meta)
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var metrics: some View {
        HStack(spacing: 10) {
            MetricCard(value: dollars(currentTrip.fare), label: "Fare", color: TravelPlannerColor.tealSoft)
            MetricCard(value: "\(currentTrip.score)", label: "Score", color: TravelPlannerColor.goldSoft)
            MetricCard(value: "\(currentTrip.days.count)", label: "Days", color: TravelPlannerColor.limeSoft)
        }
    }

    private var executionPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Execution", subtitle: "Move the trip from idea to booked")

            Picker(
                "Execution status",
                selection: Binding(
                    get: { currentTrip.executionStatus },
                    set: { viewModel.updateExecutionStatus($0, for: currentTrip) }
                )
            ) {
                ForEach(TripExecutionStatus.allCases) { status in
                    Label(status.rawValue, systemImage: status.symbol)
                        .tag(status)
                }
            }
            .pickerStyle(.segmented)
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var notesPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Notes", subtitle: "Local context for this plan")

            TextEditor(
                text: Binding(
                    get: { currentTrip.notes },
                    set: { viewModel.updateNotes($0, for: currentTrip) }
                )
            )
            .font(.body)
            .scrollContentBackground(.hidden)
            .frame(minHeight: 110)
            .padding(10)
            .background(TravelPlannerColor.paper, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var tasksPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(title: "Tasks", subtitle: "\(completedTaskCount) of \(currentTrip.tasks.count) complete")

            HStack(spacing: 8) {
                TextField("Add task", text: $newTaskTitle)
                    .textFieldStyle(.roundedBorder)
                    .submitLabel(.done)
                    .onSubmit(addTask)

                Button(action: addTask) {
                    Image(systemName: "plus")
                        .frame(width: 36, height: 36)
                }
                .buttonStyle(.borderedProminent)
                .tint(TravelPlannerColor.teal)
                .disabled(newTaskTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }

            if currentTrip.tasks.isEmpty {
                Text("No tasks yet.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(TravelPlannerColor.paper, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            } else {
                ForEach(currentTrip.tasks) { task in
                    taskRow(task)
                }
            }
        }
        .padding(14)
        .background(.white, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var completedTaskCount: Int {
        currentTrip.tasks.filter(\.isDone).count
    }

    private func taskRow(_ task: TripTask) -> some View {
        HStack(spacing: 10) {
            Button {
                viewModel.toggleTask(task, for: currentTrip)
            } label: {
                Image(systemName: task.isDone ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(task.isDone ? TravelPlannerColor.teal : .secondary)
            }
            .buttonStyle(.plain)

            Text(task.title)
                .font(.subheadline)
                .strikethrough(task.isDone)
                .foregroundStyle(task.isDone ? .secondary : .primary)
                .frame(maxWidth: .infinity, alignment: .leading)

            Button(role: .destructive) {
                viewModel.removeTask(task, from: currentTrip)
            } label: {
                Image(systemName: "trash")
                    .frame(width: 34, height: 34)
            }
            .buttonStyle(.borderless)
        }
        .padding(12)
        .background(TravelPlannerColor.paper, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private func addTask() {
        viewModel.addTask(title: newTaskTitle, to: currentTrip)
        newTaskTitle = ""
    }

    private var itinerary: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeader(
                title: "Itinerary",
                subtitle: "\(currentTrip.days.count) planned stop\(currentTrip.days.count == 1 ? "" : "s")"
            )

            ForEach(currentTrip.days) { day in
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
                viewModel.selectTrip(currentTrip)
            } label: {
                Label("Select", systemImage: "checkmark.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)

            if viewModel.isTripSaved(currentTrip) {
                Button(role: .destructive) {
                    viewModel.removeSavedTrip(currentTrip)
                    dismiss()
                } label: {
                    Label("Remove", systemImage: "trash")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            } else {
                Button {
                    viewModel.saveTrip(currentTrip)
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
