#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX 100

typedef struct {
    char name[50];
    char phone[15];
    char email[50];
} Contact;

void addContact();
void displayContacts();
void searchContact();
void deleteContact();
void editContact();

const char *filename = "contacts.dat";

int main() {
    int choice;
    do {
        printf("\n==== Contact Agenda ====");
        printf("\n1. Add Contact");
        printf("\n2. Display Contacts");
        printf("\n3. Search Contact");
        printf("\n4. Delete Contact");
        printf("\n5. Edit Contact");
        printf("\n0. Exit");
        printf("\nSelect an option: ");
        scanf("%d", &choice);
        getchar();

        switch(choice) {
            case 1: addContact(); break;
            case 2: displayContacts(); break;
            case 3: searchContact(); break;
            case 4: deleteContact(); break;
            case 5: editContact(); break;
            case 0: printf("Exiting...\n"); break;
            default: printf("Invalid option.\n");
        }
    } while(choice != 0);
    return 0;
}

// Implementaciones omitidas por espacio (puedo darte el código completo si lo deseas)