import SwiftUI

struct MemoryView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Memory",
                subtitle: viewModel.memory.isEmpty ? "Preference state" : "\(viewModel.memory.count) saved notes"
            )

            if viewModel.memory.isEmpty {
                EmptyStateView(text: "Memory is empty.")
            } else {
                ForEach(viewModel.memory) { note in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "brain.head.profile")
                            .foregroundStyle(TravelPlannerColor.coral)
                            .frame(width: 34, height: 34)
                            .background(TravelPlannerColor.coralSoft, in: Circle())

                        VStack(alignment: .leading, spacing: 4) {
                            Text(note.title)
                                .font(.subheadline.weight(.semibold))
                            Text(note.detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(12)
                    .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
