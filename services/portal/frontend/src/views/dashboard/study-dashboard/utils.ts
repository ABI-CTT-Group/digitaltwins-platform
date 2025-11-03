

export const reWriteCategoryDetails = (
    category: string
   ) => {
    switch (category) {
        case "Programmes":
            return "A Programme is an umbrella to group one or more Projects."
        case "Projects":
            return "A Project represents research activities conducted by a group of one or more people."
        case "Investigations":
            return "Investigation is a high level description of the research carried out winthin a particular project."
        case "Studies":
            return "A Study is a particular hypothesis, which you are planning to test, using various techniques. A Study must belong to one Investigation and it can contain one or more Assays."
        default:
            return "";
    }
}