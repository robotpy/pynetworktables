
#include "Commands/Scheduler.h"

Scheduler *Scheduler::_instance = NULL;

Scheduler::Scheduler()
{

}

Scheduler::~Scheduler()
{

}

Scheduler * Scheduler::GetInstance()
{
	if (Scheduler::_instance == NULL)
		Scheduler::_instance = new Scheduler();

	return Scheduler::_instance;
}

std::string Scheduler::GetName()
{
	return std::string();
}

std::string Scheduler::GetSmartDashboardType()
{
	return std::string();
}

ITable* Scheduler::GetTable()
{
	return NULL;
}

void Scheduler::InitTable(ITable* subtable)
{

}

void Scheduler::SetEnabled(bool enabled)
{
	m_enabled = enabled;
}

void Scheduler::RemoveAll()
{

}
