import SwiftUI

struct BriefFormView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(title: "Trip Brief", subtitle: "\(viewModel.origin) to \(viewModel.destination)")

            Picker("Mood", selection: $viewModel.mood) {
                ForEach(TripMood.allCases) { mood in
                    Label(mood.rawValue, systemImage: mood.symbol)
                        .tag(mood)
                }
            }
            .pickerStyle(.segmented)

            routeFields

            dateFields

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Label("Budget per person", systemImage: "creditcard")
                    Spacer()
                    Text(dollars(viewModel.budget))
                        .font(.headline)
                        .foregroundStyle(TravelPlannerColor.coral)
                }

                Slider(value: $viewModel.budget, in: 600...3_200, step: 100)
                    .tint(TravelPlannerColor.coral)
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            VStack(alignment: .leading, spacing: 8) {
                Label("Constraints", systemImage: "slider.horizontal.3")
                    .font(.subheadline.weight(.semibold))

                TextEditor(text: $viewModel.constraints)
                    .frame(minHeight: 92)
                    .scrollContentBackground(.hidden)
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            Toggle(isOn: $viewModel.rememberPreferences) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Remember preferences")
                        .font(.subheadline.weight(.semibold))
                    Text("Use saved notes during the next run")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            Button {
                Task { await viewModel.runAgent() }
            } label: {
                HStack {
                    if viewModel.isRunning {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Image(systemName: "arrow.right")
                    }
                    Text(viewModel.isRunning ? "Running agent" : "Run agent")
                }
                .font(.headline)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
            }
            .buttonStyle(.borderedProminent)
            .tint(.black)
            .disabled(viewModel.isRunning)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var routeFields: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                originField
                destinationField
            }

            VStack(spacing: 12) {
                originField
                destinationField
            }
        }
    }

    private var dateFields: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                departField
                returnField
            }

            VStack(spacing: 12) {
                departField
                returnField
            }
        }
    }

    private var originField: some View {
        FieldCard(title: "From") {
            TextField("Origin", text: $viewModel.origin)
                .textInputAutocapitalization(.words)
        }
    }

    private var destinationField: some View {
        FieldCard(title: "To") {
            TextField("Destination", text: $viewModel.destination)
                .textInputAutocapitalization(.words)
        }
    }

    private var departField: some View {
        FieldCard(title: "Depart") {
            DatePicker("Depart", selection: $viewModel.departDate, displayedComponents: .date)
                .labelsHidden()
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var returnField: some View {
        FieldCard(title: "Return") {
            DatePicker("Return", selection: $viewModel.returnDate, displayedComponents: .date)
                .labelsHidden()
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
