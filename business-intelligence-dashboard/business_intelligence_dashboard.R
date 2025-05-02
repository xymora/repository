library(shiny)
library(ggplot2)
library(dplyr)

# Cargar datos
sales_data <- read.csv("sales_dashboard_data.csv")

ui <- fluidPage(
    titlePanel("📊 Business Intelligence Dashboard"),
    sidebarLayout(
        sidebarPanel(
            selectInput("segment", "Select Segment:", choices = unique(sales_data$Segment), selected = "Consumer"),
            selectInput("region", "Select Region:", choices = unique(sales_data$Region), selected = "North")
        ),
        mainPanel(
            h3("KPI Summary"),
            verbatimTextOutput("summary"),
            plotOutput("salesPlot"),
            plotOutput("profitPlot")
        )
    )
)

server <- function(input, output) {
    filtered_data <- reactive({
        sales_data %>%
            filter(Segment == input$segment, Region == input$region)
    })
    
    output$summary <- renderPrint({
        data <- filtered_data()
        summary_df <- data %>%
            summarise(
                Total_Sales = sum(Sales),
                Total_Profit = sum(Profit),
                Total_Orders = sum(Orders),
                Avg_Order_Value = mean(Sales / Orders)
            )
        print(summary_df)
    })
    
    output$salesPlot <- renderPlot({
        data <- filtered_data()
        ggplot(data, aes(x = Orders, y = Sales)) +
            geom_point(color = "steelblue") +
            labs(title = "Orders vs Sales", x = "Number of Orders", y = "Sales")
    })
    
    output$profitPlot <- renderPlot({
        data <- filtered_data()
        ggplot(data, aes(x = Sales, y = Profit)) +
            geom_point(color = "darkgreen") +
            labs(title = "Sales vs Profit", x = "Sales", y = "Profit")
    })
}

shinyApp(ui = ui, server = server)
